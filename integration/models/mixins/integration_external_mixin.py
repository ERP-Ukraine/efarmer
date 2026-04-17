# See LICENSE file for full copyright and licensing details.

import logging

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.sql import escape_psql

from ...tools import is_translated_value
from ...exceptions import NoExternal, MultipleExternalRecordsFound


_logger = logging.getLogger(__name__)


RESULT_CREATED = 1
RESULT_ALREADY_MAPPED = 2
RESULT_MAPPED = 3
RESULT_EXISTS = 4
RESULT_NOT_IN_EXTERNAL = 5


class IntegrationExternalMixin(models.AbstractModel):
    _name = 'integration.external.mixin'
    _description = 'Integration External Mixin'
    _odoo_model = None
    _map_field = 'external_reference'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        related='integration_id.company_id',
    )
    type_api = fields.Selection(
        related='integration_id.type_api',
    )
    code = fields.Char(
        required=True,
    )
    name = fields.Char(
        string='External Name',
        help='Contains name of the External Object in selected Integration',
    )
    external_reference = fields.Char(
        string='External Reference',
        help='Contains unique code of the External Object in the external '
             'system. Used for automated mapping',
    )

    _sql_constraints = [
        (
            'uniq_code',
            'unique(integration_id, code)',
            'Code should be unique',
        ),
        # PostgreSQL treats NULLs as distinct values, therefore, this constraint won't work with
        # NULL values in a column with a UNIQUE index.
        (
            'uniq_reference',
            'unique(integration_id, external_reference)',
            'External Reference should be unique',
        ),
    ]

    @property
    def mapping_model(self):
        if not self._odoo_model:
            return None

        model_name = f'integration.{self._odoo_model}.mapping'
        return self.env[model_name] if model_name in self.env else None

    @property
    def odoo_model(self):
        assert bool(self._odoo_model), 'Class attribute `_odoo_model` not defined'
        return self.env[self._odoo_model]

    @property
    def mapping_record(self):
        return self.mapping_model._search_mapping_from_external(
            self.integration_id,
            self,
        )

    @property
    def odoo_record(self):
        return self.mapping_record.odoo_record

    def write(self, vals):
        result = super().write(vals)
        self.requeue_jobs_if_needed()
        return result

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        result.requeue_jobs_if_needed()
        return result

    def _get_integration_id_for_job(self):
        return self.integration_id.id

    def requeue_jobs_if_needed(self):
        QueueJob = self.env['queue.job']

        for external in self:
            if external.external_reference:
                QueueJob.requeue_integration_jobs(
                    'NoExternal',
                    external._name,
                    external.code,
                )

    def create_or_update_mapping(self, odoo_id=None):
        """
        :odoo_id:
            - None - just create mapping-record if not exists
            - False - create mapping-record if not exists, or unmap Odoo ID
            - int - cretae or update mapping-record + update Odoo ID
        """
        self.ensure_one()

        mapping = self.mapping_record
        internal_field_name, external_field_name = mapping._mapping_fields

        if not mapping:
            return mapping.create({
                internal_field_name: odoo_id,
                external_field_name: self.id,
                'integration_id': self.integration_id.id,
            })

        if odoo_id is not None:
            if mapping.odoo_record.id != odoo_id:
                mapping.write({internal_field_name: odoo_id})

        return mapping

    @api.model
    def create_or_update(self, vals):
        domain = [
            ('integration_id', '=', vals['integration_id']),
            ('code', '=', vals['code']),
        ]

        record = self.search(domain, limit=1)
        if record:
            record.write(vals)
            return record
        return self.create(vals)

    def _compute_display_name(self):
        for rec in self:
            value = f'(ID: {rec.code})'

            if rec.external_reference:
                value = f'{value}[{rec.external_reference}]'

            value = f'{value} {getattr(rec, rec._rec_name)}'

            rec.display_name = value

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100) -> list[tuple[int, str]]:
        """Search for records that have a display name matching the given name pattern.

        This method searches both 'name' and 'code' fields to provide flexible search
        functionality for external integration records.
        """
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', operator, name), ('code', operator, name)]

        # Use search_fetch to get records with display_name
        records = self.search_fetch(
            expression.AND([domain, args]),
            ['display_name'],
            limit=limit
        )

        # Return list of (id, display_name) tuples as expected by Odoo 18.0
        return [(record.id, record.display_name) for record in records.sudo()]

    def _map_external(self, adapter_external_data):
        if not self:
            return False

        for rec in self:
            rec.try_map_by_external_reference()

        return self._fix_unmapped(adapter_external_data)

    def try_map_by_external_reference(self, odoo_search_domain=False):
        self.ensure_one()

        # If we found existing mapping, we do not need to do anything
        odoo_record = self.odoo_record
        if odoo_record:
            return odoo_record

        self.create_or_update_mapping()
        reference = getattr(self, self._map_field)

        if reference:
            if odoo_search_domain:
                search_domain = odoo_search_domain
            else:
                search_domain = [(
                    self.integration_id._get_reference_field_name(self.odoo_model),
                    '=ilike',
                    escape_psql(reference),
                )]

            odoo_record = self.odoo_model.search(search_domain)

            if len(odoo_record) > 1:
                record_details = '\n'.join([
                    '- %(display_name)s (ID: %(id)s)' % {
                        'display_name': getattr(record, "display_name", "Unnamed Record"),
                        'id': record.id
                    }
                    for record in odoo_record
                ])

                raise ValidationError(_(
                    'Multiple Odoo records (%(model)s) found with the same internal reference:\n'
                    '%(details)s\n\n'
                    'Please review the duplicated records and resolve the issue by either removing '
                    'the unnecessary records or updating the internal reference field (%(ref_field)s) '
                    'for the appropriate records.'
                ) % {
                    'model': self.odoo_model._description,
                    'details': record_details,
                    'ref_field': self.integration_id._get_reference_field_name(self.odoo_model),
                })

        if odoo_record:
            self.create_or_update_mapping(odoo_id=odoo_record.id)

        return self.odoo_record

    def _fix_unmapped(self, adapter_external_data):
        # Method that should be overriden in needed external models
        pass

    def action_open_mapping(self):
        mapping = self.mapping_record

        return {
            'type': 'ir.actions.act_window',
            'name': mapping._description,
            'res_model': mapping._name,
            'view_mode': 'list',
            'domain': [('id', 'in', mapping.ids)],
            'target': 'current',
        }

    def create_integration_external(self, odoo_record, extra_vals=None):
        """Integration External --> Odoo"""
        self.ensure_one()

        odoo_record.create_mapping(
            self.integration_id,
            self.code,
            extra_vals=extra_vals,
        )

    @api.model
    def get_external_by_code(self, integration, code, raise_error=True):
        external = self.search([
            ('code', '=', code),
            ('integration_id', '=', integration.id),
        ])

        if raise_error:
            if not external:
                raise NoExternal(_(
                    '\nCannot find external record. Please ensure the relevant objects are imported from '
                    'the E-Commerce System.'), model_name=self._name, code=code, integration=integration
                )

            if len(external) > 1:
                raise MultipleExternalRecordsFound(
                    _('Found several external records'),
                    model_name=self._name,
                    code=code,
                    integration=integration,
                    duplicates=external,
                )

        return external

    @api.model
    def get_original_name(self, value, integration=None):
        integration = integration or self.integration_id
        translations = self.env['integration.res.lang.mapping'] \
            .convert_external_translations(integration.id, value)
        return integration._get_original_from_translations(translations)

    @api.model
    def create_or_update_with_translations(
        self,
        integration_id: int,
        odoo_object: 'models.Model',
        vals: dict,
        translations_only: bool = False,
    ):
        translations, translatable_fields, non_translatable_fields = defaultdict(dict), {}, {}

        integration = self.env['sale.integration'].browse(integration_id)
        shop_lang_code = integration.get_shop_lang_code()
        context_lang_code = integration.get_integration_lang_code()

        for field, value in vals.items():
            if is_translated_value(value):
                translatable_fields[field] = value['language']
            else:
                non_translatable_fields[field] = value

        ResLang = self.env['res.lang']
        for field, raw_translations in translatable_fields.items():
            for res_lang_id, translation in raw_translations.items():
                translation_lang_code = ResLang.browse(res_lang_id).code

                if context_lang_code == translation_lang_code:
                    non_translatable_fields[field] = translation
                else:
                    translations[translation_lang_code][field] = translation

            if field not in non_translatable_fields:
                non_translatable_fields[field] = translations[shop_lang_code][field]

        odoo_object = odoo_object \
            .with_company(integration.company_id) \
            .with_context(lang=context_lang_code)

        # Update non-translatable fields
        if odoo_object:
            if not translations_only:
                odoo_object.write(non_translatable_fields)
        else:
            odoo_object = odoo_object.create(non_translatable_fields)

        # Update translatable fields
        for lang_code, data in translations.items():
            vals = {}
            for field, value in data.items():
                vals[field] = value or non_translatable_fields[field]

            odoo_object.with_context(lang=lang_code).write(vals)

        return odoo_object

    def _pre_import_external_check(self, external_record, integration):
        return True

    def _post_import_external_one(self, adapter_external_record):
        """It's a hook method for redefining."""
        pass

    def _post_import_external_multi(self, adapter_external_record):
        """It's a hook method for redefining."""
        pass

    @api.model
    def _fix_unmapped_element(self, integration, element):
        # element - 'attribute' or 'feature'
        ElementValueMapping = self.env[f'integration.product.{element}.value.mapping']
        ExternalElement = self.env[f'integration.product.{element}.external']
        MappingElement = self.env[f'integration.product.{element}.mapping']
        ElementValue = self.env[f'product.{element}.value']

        external_values = getattr(integration.adapter, f'get_{element}_values')()

        external_values_by_id = {
            x['id']: x['id_group'] for x in external_values
        }

        # 1. Try to find unmapped "Product Attribute/Feature Value Mapping"
        mapped_element_values = ElementValueMapping.search([
            ('integration_id', '=', integration.id),
            (element + '_value_id', '=', False),
        ])

        for mapped_element_value in mapped_element_values:
            # 2. Get "Product Attribute/Feature Value External"
            external_element_value = getattr(mapped_element_value, f'external_{element}_value_id')

            if not external_element_value:
                continue

            external_element_code = external_values_by_id.get(external_element_value.code, None)

            # 3. Get "Product Attribute/Feature External" by Code (External ID)
            external_element = ExternalElement.search([
                ('integration_id', '=', integration.id),
                ('code', '=', external_element_code)
            ])

            if not external_element:
                continue

            # 4. Get by mapping "Product Attribute/Feature" by Code (External ID)
            value = MappingElement.search([
                ('integration_id', '=', integration.id),
                (f'external_{element}_id', '=', external_element.id),
            ]).mapped(f'{element}_id')

            if not value or len(value) != 1:
                continue

            # 5. Get "Product Attribute/Feature Value" by Name
            product_element_value = ElementValue.search([
                (f'{element}_id', '=', value.id),
                ('name', '=ilike', escape_psql(external_element_value.name)),
            ])

            if product_element_value and len(product_element_value) == 1:
                # 6. Set attribute_value_id or feature_value_id
                setattr(mapped_element_value, element + '_value_id', product_element_value)

    @api.model
    def _fix_unmapped_element_values(self, integration, element):
        """
        This method tries to map unmapped "Product Attribute/Feature Value Mapping" for
        already mapped "Product Attribute/Feature Mapping".

        This is useful for cases when we have some "Product Attribute/Feature" already existed
        in Odoo while importing them from external system. In this case, their values are not
        mapped. This method tries to map them.

        element: 'attribute' or 'feature'
        """
        if element not in ('attribute', 'feature'):
            raise UserError(_(
                'The value must be either "attribute" or "feature". This is a technical issue '
                'that cannot be fixed through configuration and requires investigation by our developers. '
                'If you encounter this error, please contact our support team: https://support.ventor.tech/'
            ))

        ElementValueMapping = self.env[f'integration.product.{element}.value.mapping']
        ElementMapping = self.env[f'integration.product.{element}.mapping']
        ElementValue = self.env[f'product.{element}.value']

        # 1. Find all mapped "Product Attribute/Feature Mapping"
        mapped_elements = ElementMapping.search([
            ('integration_id', '=', integration.id),
            (element + '_id', '!=', False),
        ])

        for mapped_element in mapped_elements:
            # 2. Try to map unmapped "Product Attribute/Feature Value Mapping"
            # Find all external "Product Attribute/Feature Value Mapping" for current element
            external_element = getattr(mapped_element, f'external_{element}_id')
            external_element_values = getattr(external_element, f'external_{element}_value_ids')

            unmapped_element_values = ElementValueMapping.search([
                ('integration_id', '=', integration.id),
                (f'external_{element}_value_id', 'in', external_element_values.ids),
                (element + '_value_id', '=', False),
            ])

            for unmapped_element_value in unmapped_element_values:
                # 3. Try to find "Product Attribute/Feature Value" by Name or create
                external_field_name = unmapped_element_value._mapping_fields[1]
                name = getattr(unmapped_element_value, external_field_name).name

                internal_field_name = mapped_element._mapping_fields[0]
                element_id = getattr(mapped_element, internal_field_name)

                element_value = ElementValue.search([
                    (f'{element}_id', '=', element_id.id),
                    ('name', '=ilike', escape_psql(name)),
                ], limit=1)

                if not element_value:
                    sequence_value = getattr(mapped_element, f'{element}_id')._get_next_sequence()

                    element_value = self.create_or_update_with_translations(
                        self.integration_id.id,
                        ElementValue,
                        {
                            'name': name,
                            'sequence': sequence_value,
                            f'{element}_id': element_id.id,
                        },
                    )

                # 4. Try to map unmapped "Product Attribute/Feature Value Mapping"
                external_record = getattr(unmapped_element_value, f'external_{element}_value_id')
                external_record.create_or_update_mapping(odoo_id=element_value.id)

    def _post_import_external_element(self, adapter_external_record, element):
        """
        This method will receive individual attribute/feature value record.
        And link external attribute/feature value with external attribute/feature
        element - 'attribute' or 'feature'
        """
        # 1. Try to get Code (External ID) of Value
        element_code = adapter_external_record.get('id_group')
        if not element_code:
            raise UserError(_(
                'External %s value is missing the required "id_group" field. '
                'This is a technical issue with the data received from the e-commerce system. '
                'Please contact our support team to investigate the issue: https://support.ventor.tech/'
            ) % element.capitalize())

        # 2. Get "Product Attribute/Feature External" by Code (External ID)
        external_element = self.env[f'integration.product.{element}.external'].search([
            ('code', '=', element_code),
            ('integration_id', '=', self.integration_id.id),
        ])

        if not external_element:
            raise UserError(_(
                'No External Product %s found with code %s. '
                'It is possible that %ss have not been imported yet. '
                'Please ensure that %ss are imported from the e-commerce system.\n'
                'If the issue persists, contact support: https://support.ventor.tech/'
            ) % (element.capitalize(), element_code, element, element))

        if len(external_element) != 1:
            raise UserError(_(
                'Multiple or no external %s records found for code %s. '
                'This is a technical issue that requires investigation. '
                'Please contact our support team for assistance: https://support.ventor.tech/'
            ) % (element.capitalize(), element_code))

        # 3. Set external_attribute_id or external_feature_id
        setattr(self, f'external_{element}_id', external_element.id)

    def _import_elements_and_values(self, ext_element, ext_values, element, link_to_existing=False):
        result = {
            'element': 0,
            'values': {RESULT_ALREADY_MAPPED: 0, RESULT_MAPPED: 0, RESULT_CREATED: 0},
        }
        MappingProductElement = self.env[f'integration.product.{element}.mapping']
        MappingProductElementValue = self.env[f'integration.product.{element}.value.mapping']
        ExternalProductElementValue = self.env[f'integration.product.{element}.value.external']

        # Add to context the default integration language for the further search methods.
        context_lang_code = self.integration_id.get_integration_lang_code()
        ProductElement = self.env[f'product.{element}'] \
            .with_context(lang=context_lang_code)
        ProductElementValue = self.env[f'product.{element}.value'] \
            .with_context(lang=context_lang_code)

        # 1. Checks before creating
        element_mapping = MappingProductElement.get_mapping(self.integration_id, self.code)

        element_record = None
        # 1.1. Check that attribute/feature already mapped
        if element_mapping:
            element_record = getattr(element_mapping, f'{element}_id')

        # Important! The ProductElement variable has context language from integration.
        odoo_object = ProductElement.search([('name', '=ilike', escape_psql(self.name))])

        # 1.2. Check by Name that attribute/feature already exists in Odoo
        if odoo_object and not element_record and not link_to_existing:
            result['element'] = RESULT_EXISTS
            return result

        # 2. Create Product Attribute/Feature (if it is not already created)
        if element_record:
            result['element'] = RESULT_ALREADY_MAPPED
        else:
            name = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(self.integration_id.id, ext_element['name'])

            vals = dict(name=name)
            if element == 'attribute':
                mode_value = self._get_mode_create_variant(ext_element['id'], ext_values)
                vals['create_variant'] = mode_value

            element_record = self.create_or_update_with_translations(
                self.integration_id.id,
                odoo_object,
                vals,
            )

            # Create mapping for new attribute
            self.create_or_update_mapping(odoo_id=element_record.id)

            # Warn if this Odoo record already has a mapping to a different external record
            existing_mappings = MappingProductElement.search([
                ('integration_id', '=', self.integration_id.id),
                (f'{element}_id', '=', element_record.id),
            ])
            if len(existing_mappings) > 1:
                external_field = f'external_{element}_id'
                existing_codes = [getattr(m, external_field).code for m in existing_mappings]
                _logger.warning(
                    'Multiple external %s records mapped to the same Odoo record '
                    '"%s" (id=%s) for integration "%s". External codes: %s.',
                    element, element_record.name, element_record.id,
                    self.integration_id.name, existing_codes,
                )

            result['element'] = RESULT_CREATED

        # 3. Create Product Attribute/Feature Values
        for ext_value in ext_values:
            # 4. Checks before creating
            element_value_mapping = \
                MappingProductElementValue.get_mapping(self.integration_id, ext_value['id'])

            element_value = None
            # 4.1. Check that attribute already mapped
            if element_value_mapping:
                element_value = getattr(element_value_mapping, f'{element}_value_id')

            if element_value:
                result['values'][RESULT_ALREADY_MAPPED] += 1
                continue

            # 5. Try to find "Product Attribute/Feature Value" by Name or create
            name = ext_value['name']
            if isinstance(name, dict) and name.get('language'):
                name = self.get_original_name(name)

            # Important! The ProductElementValue variable has context language from integration.
            element_value = ProductElementValue.search([
                (f'{element}_id', '=', element_record.id),
                ('name', '=ilike', escape_psql(name)),
            ])

            if element_value:
                result['values'][RESULT_MAPPED] += 1
            else:
                name = self.env['integration.res.lang.mapping'] \
                    .convert_external_translations(self.integration_id.id, ext_value['name'])

                sequence_value = element_record._get_next_sequence()

                element_value = self.create_or_update_with_translations(
                    self.integration_id.id,
                    ProductElementValue,
                    {
                        'name': name,
                        'sequence': sequence_value,
                        f'{element}_id': element_record.id,
                    },
                )
                result['values'][RESULT_CREATED] += 1

            # 6.  Get external record and if it doesn't exists create it
            external_value = ExternalProductElementValue.get_external_by_code(
                self.integration_id,
                ext_value['id'],
                raise_error=False,
            )

            if not external_value:
                external_value = ExternalProductElementValue.create({
                    'code': ext_value['id'],
                    'name': element_value.name,
                    'integration_id': self.integration_id.id,
                })

            # 7. Create mapping for new product attribute/feature value
            external_value.create_or_update_mapping(odoo_id=element_value.id)

        return result

    def _run_import_elements_element(self, element, link_to_existing=False):
        res_element = {}
        res_values = {}
        elements_by_integration = {}
        msg = ''

        # Distribute selected attributes/features by connectors
        for external_element in self:
            integration_id = external_element.integration_id.id

            if integration_id not in elements_by_integration:
                elements_by_integration[integration_id] = {
                    'integration': external_element.integration_id,
                    'elements': []
                }

            elements_by_integration[integration_id]['elements'] += [external_element]

        for integration_id, external_elements in elements_by_integration.items():
            adapter = external_elements['integration'].adapter

            # Get attributes and values from External System
            ext_elements = getattr(adapter, f'get_{element}s')()
            ext_values = getattr(adapter, f'get_{element}_values')()

            # Create dict with selected attributes/features
            # and attributes/features + values from External System
            elements_dict = {
                external_element.code: {
                    'ext_elements': {},
                    'ext_values': [],
                    'external_element': external_element
                }
                for external_element in external_elements['elements']
            }

            for ext_element in ext_elements:
                if ext_element['id'] in elements_dict:
                    elements_dict[ext_element['id']]['ext_elements'] = ext_element

            for ext_value in ext_values:
                if ext_value['id_group'] in elements_dict:
                    elements_dict[ext_value['id_group']]['ext_values'] += [ext_value]

            # Run through the attributes and try to import them
            for key, item in elements_dict.items():
                external_element = item['external_element']

                if not item['ext_elements']:
                    result = {'element': RESULT_NOT_IN_EXTERNAL, 'values': {}}
                else:
                    result = external_element._import_elements_and_values(
                        item['ext_elements'],
                        item['ext_values'],
                        element,
                        link_to_existing=link_to_existing,
                    )

                if result['element'] in (RESULT_ALREADY_MAPPED, RESULT_CREATED):
                    res_element[result['element']] = res_element.get(result['element'], 0) + 1
                else:
                    res_element[result['element']] = res_element.get(result['element'], []) + \
                        [external_element.name]

                for key, value_result in result['values'].items():
                    res_values[key] = res_values.get(key, 0) + value_result

        # Create message
        if res_element.get(RESULT_CREATED) or res_values.get(RESULT_CREATED):
            msg += _('\n\nImported:\n - Product %ss: %s\n - Product %s Values: %s') % (
                element.capitalize(),
                res_element.get(RESULT_CREATED, 0),
                element.capitalize(),
                res_values.get(RESULT_CREATED, 0),
            )

        if res_element.get(RESULT_ALREADY_MAPPED) or res_values.get(RESULT_ALREADY_MAPPED):
            msg += _('\n\nAlready mapped:\n - Product %ss: %s\n - Product %s Values: %s') % (
                element.capitalize(),
                res_element.get(RESULT_ALREADY_MAPPED, 0),
                element.capitalize(),
                res_values.get(RESULT_ALREADY_MAPPED, 0),
            )

        if res_element.get(RESULT_MAPPED):
            msg += _('\n\nProduct %ss Values mapped: %s') % (
                element.capitalize(), res_element.get(RESULT_MAPPED))

        if res_element.get(RESULT_EXISTS):
            msg += _('\n\nProduct %ss already existing in Odoo:\n - ') % element.capitalize()
            msg += '%s' % '\n - '.join(res_element.get(RESULT_EXISTS))

        if res_element.get(RESULT_NOT_IN_EXTERNAL):
            msg += _('\n\nProduct %ss that do not exist in E-Commerce System:\n - ') \
                % element.capitalize()
            msg += '%s' % '\n - '.join(res_element.get(RESULT_NOT_IN_EXTERNAL))

        message_id = self.env['message.wizard'].create({'message': msg[2:]})

        return {
            'name': _('Import Product %ss') % element.capitalize(),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard',
            'res_id': message_id.id,
            'target': 'new'
        }

    def _unmap(self):
        return self.mapping_record._unmap()
