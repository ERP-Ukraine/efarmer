# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools.sql import escape_psql

from odoo.addons.integration.models.mixins.integration_external_mixin import (
    RESULT_CREATED,
    RESULT_ALREADY_MAPPED,
    RESULT_MAPPED,
    RESULT_EXISTS,
    RESULT_NOT_IN_EXTERNAL,
    RESULT_MODE_CONFLICT,
)

_logger = logging.getLogger(__name__)


class IntegrationProductAttributeExternal(models.Model):
    _name = 'integration.product.attribute.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Attribute External'
    _odoo_model = 'product.attribute'
    _map_field = 'name'

    external_attribute_value_ids = fields.One2many(
        comodel_name='integration.product.attribute.value.external',
        inverse_name='external_attribute_id',
        string='External Attribute Values',
        readonly=True,
    )

    used_for_variants = fields.Boolean(
        string='Used for Variants',
        default=True,
    )

    def run_import_attributes(self):
        return self._run_import_attributes(link_to_existing=True)

    def _get_mode_create_variant(self, *args, **kw):
        if self.integration_id.is_import_dynamic_attribute:
            return 'dynamic'
        return 'always'

    def try_map_by_external_reference(self, odoo_search_domain=False):
        self.ensure_one()

        # Auto-map only to an Odoo attribute whose "Variant Creation" mode is
        # compatible with this external attribute (a variation attribute to one
        # that creates variants, a descriptive one to a "Never" attribute), so
        # by-name auto-mapping never links to a same-name attribute of the wrong
        # mode (which the mapping constraint would otherwise reject).
        if not odoo_search_domain:
            reference = getattr(self, self._map_field)
            if reference:
                reference_field = self.integration_id._get_reference_field_name(self.odoo_model)
                odoo_search_domain = [(reference_field, '=ilike', escape_psql(reference))]
                if self.used_for_variants:
                    odoo_search_domain += [('create_variant', '!=', 'no_variant')]
                else:
                    odoo_search_domain += [('create_variant', '=', 'no_variant')]

        return super().try_map_by_external_reference(odoo_search_domain=odoo_search_domain)

    # -- Import of attributes and their values ---------------------------------
    # This used to be handled by the generic ``element``-based methods on the
    # mixin. It now lives here so the attribute-specific logic (the Variant
    # Creation mode) reads top-to-bottom without string indirection.

    def _run_import_attributes(self, link_to_existing=False):
        res_element = {}
        res_values = {}

        attributes_by_integration = {}
        for external_attribute in self:
            integration = external_attribute.integration_id
            attributes_by_integration[integration] = \
                attributes_by_integration.get(integration, self.browse()) | external_attribute

        for integration, external_attributes in attributes_by_integration.items():
            adapter = integration.adapter

            ext_attributes = adapter.get_attributes()
            ext_values = adapter.get_attribute_values()

            attributes_dict = {
                external_attribute.code: {
                    'ext_attribute': {},
                    'ext_values': [],
                    'external_attribute': external_attribute,
                }
                for external_attribute in external_attributes
            }

            for ext_attribute in ext_attributes:
                if ext_attribute['id'] in attributes_dict:
                    attributes_dict[ext_attribute['id']]['ext_attribute'] = ext_attribute

            for ext_value in ext_values:
                if ext_value['id_group'] in attributes_dict:
                    attributes_dict[ext_value['id_group']]['ext_values'].append(ext_value)

            for item in attributes_dict.values():
                external_attribute = item['external_attribute']

                if not item['ext_attribute']:
                    result = {'element': RESULT_NOT_IN_EXTERNAL, 'values': {}}
                else:
                    result = external_attribute._import_attribute_and_values(
                        item['ext_attribute'],
                        item['ext_values'],
                        link_to_existing=link_to_existing,
                    )

                if result['element'] in (RESULT_ALREADY_MAPPED, RESULT_CREATED):
                    res_element[result['element']] = res_element.get(result['element'], 0) + 1
                else:
                    res_element[result['element']] = \
                        res_element.get(result['element'], []) + [external_attribute.name]

                for code, value_result in result['values'].items():
                    res_values[code] = res_values.get(code, 0) + value_result

        return self._build_import_elements_action(_('Attribute'), res_element, res_values)

    def _import_attribute_and_values(self, ext_attribute, ext_values, link_to_existing=False):
        self.ensure_one()

        result = {
            'element': 0,
            'values': {RESULT_ALREADY_MAPPED: 0, RESULT_MAPPED: 0, RESULT_CREATED: 0},
        }

        Mapping = self.env['integration.product.attribute.mapping']
        MappingValue = self.env['integration.product.attribute.value.mapping']
        ExternalValue = self.env['integration.product.attribute.value.external']

        # Important! These models carry the integration language for the searches below.
        context_lang_code = self.integration_id.get_integration_lang_code()
        ProductAttribute = self.env['product.attribute'].with_context(lang=context_lang_code)
        ProductAttributeValue = self.env['product.attribute.value'].with_context(lang=context_lang_code)

        # The mode this external attribute should be imported as. Keep the
        # "Used for Variants" flag in sync with it so the mapping constraint and
        # the by-name auto-mapping can rely on the flag for every connector.
        mode = self._get_mode_create_variant(ext_attribute['id'], ext_values)
        used_for_variants = mode != 'no_variant'
        if self.used_for_variants != used_for_variants:
            self.used_for_variants = used_for_variants

        # 1. Is this external attribute already mapped to an Odoo attribute?
        attribute_mapping = Mapping.get_mapping(self.integration_id, self.code)
        odoo_attribute = attribute_mapping.attribute_id if attribute_mapping else None

        # 2. Match an existing Odoo attribute by name AND a compatible "Variant
        #    Creation" mode: a descriptive attribute must map to a "Never"
        #    attribute, a variation attribute to a variant-creating one.
        name_domain = [('name', '=ilike', escape_psql(self.name))]
        if mode == 'no_variant':
            mode_domain = [('create_variant', '=', 'no_variant')]
        else:
            mode_domain = [('create_variant', '!=', 'no_variant')]
        matched_attribute = ProductAttribute.search(name_domain + mode_domain)

        # 2.1. No compatible-mode match. If auto-linking and a same-name attribute
        #      exists in a different mode, leave this external attribute unmapped
        #      rather than link to it and silently change its mode.
        if not matched_attribute and not odoo_attribute and link_to_existing:
            if ProductAttribute.search(name_domain, limit=1):
                _logger.info(
                    'Skipping external attribute "%s" (code %s, integration "%s"): a same-name '
                    'Odoo attribute exists with a different Variant Creation mode.',
                    self.name, self.code, self.integration_id.name,
                )
                result['element'] = RESULT_MODE_CONFLICT
                return result

        # 2.2. Found by name, but auto-linking is off -> report it as existing.
        if matched_attribute and not odoo_attribute and not link_to_existing:
            result['element'] = RESULT_EXISTS
            return result

        if len(matched_attribute) > 1 and not odoo_attribute:
            raise UserError(_(
                'Multiple Odoo Attribute records share the name "%s" (IDs: %s). '
                'Please ensure each Attribute name is unique in Odoo before running the import, '
                'or manually create the mapping in the integration settings.'
            ) % (
                self.name,
                ', '.join(str(record.id) for record in matched_attribute),
            ))

        # 3. Create the Odoo attribute (or reuse the already mapped one).
        if odoo_attribute:
            result['element'] = RESULT_ALREADY_MAPPED
        else:
            name = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(self.integration_id.id, ext_attribute['name'])

            vals = {'name': name}
            # The Variant Creation mode is applied only when creating a brand-new
            # attribute - importing must never change the mode of an attribute
            # that already exists in Odoo.
            if not matched_attribute:
                vals['create_variant'] = mode

            odoo_attribute = self.create_or_update_with_translations(
                self.integration_id.id,
                matched_attribute,
                vals,
            )

            self.create_or_update_mapping(odoo_id=odoo_attribute.id)

            # Warn if this Odoo attribute is now mapped from several external records.
            existing_mappings = Mapping.search([
                ('integration_id', '=', self.integration_id.id),
                ('attribute_id', '=', odoo_attribute.id),
            ])
            if len(existing_mappings) > 1:
                _logger.warning(
                    'Multiple external attribute records mapped to the same Odoo attribute '
                    '"%s" (id=%s) for integration "%s". External codes: %s.',
                    odoo_attribute.name, odoo_attribute.id, self.integration_id.name,
                    [mapping.external_attribute_id.code for mapping in existing_mappings],
                )

            result['element'] = RESULT_CREATED

        # 4. Create or link the attribute values.
        for ext_value in ext_values:
            value_mapping = MappingValue.get_mapping(self.integration_id, ext_value['id'])
            if value_mapping and value_mapping.attribute_value_id:
                result['values'][RESULT_ALREADY_MAPPED] += 1
                continue

            name = ext_value['name']
            if isinstance(name, dict) and name.get('language'):
                name = self.get_original_name(name)

            attribute_value = ProductAttributeValue.search([
                ('attribute_id', '=', odoo_attribute.id),
                ('name', '=ilike', escape_psql(name)),
            ])

            if attribute_value:
                result['values'][RESULT_MAPPED] += 1
            else:
                name = self.env['integration.res.lang.mapping'] \
                    .convert_external_translations(self.integration_id.id, ext_value['name'])

                attribute_value = self.create_or_update_with_translations(
                    self.integration_id.id,
                    ProductAttributeValue,
                    {
                        'name': name,
                        'sequence': odoo_attribute._get_next_sequence(),
                        'attribute_id': odoo_attribute.id,
                    },
                )
                result['values'][RESULT_CREATED] += 1

            external_value = ExternalValue.get_external_by_code(
                self.integration_id,
                ext_value['id'],
                raise_error=False,
            )
            if not external_value:
                external_value = ExternalValue.create({
                    'code': ext_value['id'],
                    'name': attribute_value.name,
                    'integration_id': self.integration_id.id,
                })

            external_value.create_or_update_mapping(odoo_id=attribute_value.id)

        return result
