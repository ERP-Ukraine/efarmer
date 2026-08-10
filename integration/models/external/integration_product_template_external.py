# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from time import time
from typing import List, Dict

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.sql import escape_psql
from odoo.tools.misc import clean_context

from ...tools import _compute_checksum, ExternalImage, IS_FALSE
from ...exceptions import ErrorStore as es


_logger = logging.getLogger(__name__)


class IntegrationProductTemplateExternal(models.Model):
    _name = 'integration.product.template.external'
    _inherit = ['integration.external.mixin', 'integration.product.external.mixin']
    _description = 'Integration Product Template External'
    _odoo_model = 'product.template'
    _external_label = 'Product Template'

    external_barcode = fields.Char(
        string='Barcode',
    )

    external_product_variant_ids = fields.One2many(
        comodel_name='integration.product.product.external',
        inverse_name='external_product_template_id',
        string='External Product Variants',
        readonly=True,
    )

    timestamp_export = fields.Integer(
        string='Timestamp Export',
        required=True,
        default=0,
    )

    timestamp_export_datetime = fields.Datetime(
        string='Last Export Time',
        compute='_compute_timestamp_export_datetime',
    )

    @api.depends('timestamp_export')
    def _compute_timestamp_export_datetime(self):
        for rec in self:
            rec.timestamp_export_datetime = datetime.fromtimestamp(rec.timestamp_export)

    @property
    def child_ids(self):
        integration = self.integration_id
        variants = self.external_product_variant_ids

        if integration.type_api == 'shopify' and len(variants) == 1:
            return variants.browse()

        return variants.filtered(
            lambda x: x.code != self.get_one_variant_code()
        )

    @property
    def is_configurable(self):
        return bool(self.child_ids)

    @property
    def current_time(self):
        return int(time())

    def update_timestamp_export(self):
        self.timestamp_export = self.current_time

    def get_one_variant_code(self):
        return f'{self.code}-{IS_FALSE}'

    def action_open_import_wizard(self):
        wizard = self.create_import_wizard()
        return wizard.open_form()

    def create_import_wizard(self):
        self.ensure_one()
        wizard = self.env['integration.import.product.wizard'].create({
            'external_template_id': self.id,
        })
        wizard._create_internal_lines()

        return wizard

    def format_recordset(self):
        values = self.mapped(
            lambda x: ', '.join([
                f'id={x.id}',
                f'code={x.code}',
                f'reference={x.external_reference}',
                f'barcode={x.external_barcode}',
                f'variants={x.external_product_variant_ids.format_recordset()}',
            ])
        )
        return '[%s]' % '; '.join(f'({x})' for x in values)

    def run_import_products(self, trigger_export_other=False):
        for record in self:
            integration = record.integration_id
            job_kwargs = integration._job_kwargs_import_product(record.code, record.name)
            job_kwargs['priority'] = 2

            context = {
                'company_id': record.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'product',
                'job_external_template_id': record.id,
            }
            integration \
                .with_context(**context) \
                .with_delay(**job_kwargs) \
                .import_product(
                    record.id,
                    import_images=integration.allow_import_images,
                    trigger_export_other=trigger_export_other,
                )

        if len(self) == 1:
            message = _('Queue Job "Product Import" is created')
        else:
            message = _('Queue Jobs "Product Import" are created')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Product'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def import_one_product_by_hook(self, check_hook_gap: bool = False):
        self.ensure_one()
        integration = self.integration_id

        if check_hook_gap:
            export_timedelta = integration.get_settings_value('receive_webhook_gap', default_value=0)
            if (self.current_time - self.timestamp_export) <= int(export_timedelta):
                _logger.info(
                    '%s: Product with code=%s is not updated because the hook gap is less than the export timedelta',
                    integration.name,
                    self.code,
                )
                return False

        return self.import_one_product(import_images=integration.allow_import_images)

    def import_one_product(self, import_images=True):
        self.ensure_one()

        template_data, variants_data, bom_data, external_images = self.integration_id.adapter\
            .get_product_for_import(self.code)

        return self.with_context(integration_import_images=import_images) \
            ._import_one_product(template_data, variants_data, bom_data, external_images)

    def _import_one_product(
        self,
        template_data,
        variants_data: list,
        bom_data: list,
        external_images: List[ExternalImage],
    ):
        integration = self.integration_id
        self = self.with_context(skip_product_export=True)
        import_images = self.env.context.get('integration_import_images')

        # 1. Try map template and variants
        template = self.with_context(
            skip_mapping_update=True,
            default_operation_mode='import',
        ).try_map_template_and_variants((template_data, variants_data, bom_data, external_images))

        # 2. Update or create template with received data
        first_time_template_import = not template

        if template:
            template = template.with_context(integration_first_time_import=first_time_template_import)
            self._update_template_from_external(template, template_data)
        else:
            template = self.with_context(integration_first_time_import=True) \
                ._create_template(template_data)

        # If template is not active, then we have to update it with the context `active_test=False`
        # because variants will be archived (this is default behavior of Odoo)
        if not template.active:
            template = template.with_context(active_test=False)

        # If no variants-data --> update mapping for the default Odoo variant
        if not variants_data:
            self._try_to_update_mappings(template)

        external_variants = self.env['integration.product.product.external']

        # 3. Find and update all the variants with received data
        for variant_data in variants_data:
            # 3.1 Find external record by `complex-code`
            code = integration.adapter._build_product_external_code(
                template_data['id'], variant_data['id'])

            external_variant = self.external_product_variant_ids \
                .filtered(lambda x: x.code == code)

            assert external_variant, _('External variant %s not found') % code

            # 3.2 Find suitable variant among template childs.
            variant = external_variant._find_suitable_variant(template.product_variant_ids)

            if variant:
                values = variant \
                    .with_context(integration_first_time_import=first_time_template_import) \
                    .calculate_import_fields_data(integration.id, template_data, variant_data)
            else:
                # 3.2.1 Create the new variant if Odoo didn't create it automatically because of
                # the dynamic-attributes and the `integration_first_time_import` context variable
                variant = self.env['product.product'] \
                    .with_context(integration_first_time_import=True) \
                    .create({'product_tmpl_id': template.id})

                values = variant.calculate_import_fields_data(
                    integration.id, template_data, variant_data,
                )

                attribute_values = template._get_template_attribute_values(
                    integration.id,
                    variant_data['_attribute_value_ids'],
                )

                values.update(
                    product_tmpl_id=template.id,
                    product_template_attribute_value_ids=[(6, 0, attribute_values.ids)],
                )

            # 3.3 Create / Update variant with actual values
            variant = external_variant.create_or_update_with_translations(integration.id, variant, values)

            # 3.4 Link external record to odoo record (make mapping)
            external_variant.create_or_update_mapping(odoo_id=variant.id)
            external_variants |= external_variant

        # 5. Handle kit components
        if bom_data:
            self._create_boms(template, bom_data)

        # 5. Receive images
        self._process_images_in(external_images, receive_binaries=import_images)

        template.with_context(
            clean_context(template.env.context)
        ).import_template_hook(integration.id, force_import=first_time_template_import)

        return template

    def action_reimport_products(self):
        external_ids = []
        integration = self.mapped('integration_id')
        if len(integration) > 1:
            raise UserError(_(
                'Selected products have different integrations.\n'
                'Please select products from the same integration.'
            ))

        records = self.filtered(lambda x: not x.odoo_record)
        external_ids = records.mapped('code')

        integration.import_products_in_background(external_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reimport Product'),
                'message': _('Products import jobs are created'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _process_images_in(self, external_images: List[ExternalImage], receive_binaries=False):
        self._mark_image_mappings_as_pending()

        # 1 Update images externals/mappings
        self._update_image_mappings_in([x for x in external_images if x.is_template])

        for external_variant in self.child_ids:
            simple_variant_code = external_variant.variant_code

            external_variant._update_image_mappings_in(
                [x for x in external_images if x.is_variant and x.variant_code == simple_variant_code]
            )

        self._unlink_image_mappings_pending()

        # 2 Receive binary data
        if receive_binaries:
            mappings = self.all_image_mapping_ids.filtered(lambda x: x.sync_required)

            if mappings:
                template = self.odoo_record\
                    .with_context(default_integration_id=self.integration_id.id)

                job_kwargs = self.integration_id._job_kwargs_import_images(template)

                context = {
                    'company_id': self.company_id.id,
                    'job_integration_id': self.integration_id.id,
                    'job_integration_job_type': 'product',
                    'job_template_id': template.id,
                }
                self \
                    .with_context(**context) \
                    .with_delay(**job_kwargs) \
                    .receive_images_data()
            else:
                self._drop_abandoned_images()

        return self.all_image_mapping_ids

    def receive_images_data(self):
        self.ensure_one()

        mappings = self._sync_images_data_in()
        self._drop_abandoned_images()

        return mappings

    def _sync_images_data_in(self):
        data = dict()
        adapter = self.integration_id.adapter

        # Update images mappings with received data
        for mapping in self.all_image_mapping_ids.sorted(lambda x: x.is_template, reverse=True):
            if not mapping.sync_required:
                continue

            src = mapping.src

            if src not in data:
                b64_bytes = adapter.get_image_data(src)
                data[src] = b64_bytes

            b64_bytes = data[src]
            if not b64_bytes:
                _logger.warning('%s: Image data is empty for the image source: %s', self.integration_id.name, src)

            mapping.with_context(skip_product_export=True) \
                .apply_binary_data(b64_bytes)

            mapping.set_checksum(b64_bytes)

        return self.all_image_mapping_ids

    def _sync_images_data_out(self, datacls_list: List[ExternalImage]) -> List[Dict]:
        datacls_list_updated = self.integration_id.adapter.export_template_images(
            self.code,
            datacls_list,
            external_template_sku=self.external_reference,
            external_variant_sku_list=self.child_ids.mapped('external_reference'),
        )

        for datacls in datacls_list_updated:
            mapping = self.env['integration.ecommerce.product.image.mapping'] \
                .browse(datacls.product_image_mapping_id)

            mapping.write(datacls._to_mapping_dict())
            mapping.mark_none()

        self._unlink_image_mappings_pending()

        return [x.to_dict() for x in datacls_list_updated]

    def _drop_abandoned_images(self):
        template = self.odoo_record

        # 1.Clear template
        to_unlink_images = template.integration_template_image_ids

        if not self.all_image_mapping_ids.filtered(lambda x: x.is_template and x.is_cover):
            # Drop the main image if it is not in the external system and not belongs to any variant
            if template.image_1920:
                template_checksum = _compute_checksum(template.image_1920)

                variant_checksums = self.all_image_mapping_ids\
                    .filtered(lambda x: x.is_variant and x.is_cover) \
                    .mapped('checksum')

                if template_checksum not in variant_checksums:
                    template.image_1920 = False

        # 2. Clear variants
        for rec in template.product_variant_ids:
            to_unlink_images |= rec.integration_variant_image_ids

            if not self.all_image_mapping_ids.filtered(
                lambda x: x.is_variant and x.res_id == rec.id and x.is_cover
            ):
                rec.image_variant_1920 = False

        images = self.all_image_mapping_ids.mapped('image_id')

        return (to_unlink_images - images).unlink()

    def _update_template_from_external(self, template: models.Model, template_data: dict):
        integration = self.integration_id
        attr_values_ids_by_attr_id = integration.convert_external_attributes(
            template_data['_attributes']
        )

        # 1. Update template attributes (actualize variants count)
        for attr_id, value_ids in attr_values_ids_by_attr_id.items():
            existing_line = template.attribute_line_ids\
                .filtered(lambda x: x.attribute_id.id == attr_id)

            if existing_line:
                if set(existing_line.value_ids.ids) != set(value_ids):
                    existing_line.value_ids = [(6, 0, value_ids)]
            else:
                template.attribute_line_ids = [(0, 0, {
                    'attribute_id': attr_id,
                    'value_ids': [(6, 0, value_ids)],
                })]

        self._remove_obsolete_no_variant_attribute_lines(template, set(attr_values_ids_by_attr_id))

        # 2. Update template with actual values
        values = template.calculate_import_fields_data(integration.id, template_data)
        template = self.create_or_update_with_translations(integration.id, template, values)

        return template

    def _remove_obsolete_no_variant_attribute_lines(self, template, imported_attribute_ids):
        """Hook: drop "Never" (no_variant) attribute lines no longer present in the
        external product.

        No-op by default so importing never deletes attributes for connectors that
        do not manage their removal. Connectors opt in - see the WooCommerce
        descriptive-attribute sync, where Odoo mirrors the store. Only no_variant
        attributes are ever in scope; variation attributes are never removed here
        (that would delete and recreate variants).
        """
        return

    def _create_template(self, template_data: dict):
        integration = self.integration_id

        values = self.env['product.template'] \
            .calculate_import_fields_data(integration.id, template_data)

        if integration.apply_company_on_product and not values.get('company_id'):
            values['company_id'] = integration.company_id.id

        attr_values_ids_by_attr_id = integration.convert_external_attributes(
            template_data['_attributes']
        )

        attribute_line_ids = [
            (0, 0, {
                'attribute_id': attr_id,
                'value_ids': [(6, 0, value_ids)],
            }) for attr_id, value_ids in attr_values_ids_by_attr_id.items()
        ]
        if attribute_line_ids:
            values['attribute_line_ids'] = attribute_line_ids

        template = self.create_or_update_with_translations(integration.id, self.env['product.template'], values)

        self.create_or_update_mapping(odoo_id=template.id)

        return template

    def try_map_template_and_variants(self, ext_template_data):
        self.ensure_one()

        if not self.env.context.get('skip_mapping_validation'):
            wizard = self.create_import_wizard()
            wizard.check(external_data=ext_template_data)
            wizard.approve(force=False)

        return self._try_to_map_template_and_variants()

    def _try_to_map_template_and_variants(self):
        self._self_validation()

        template = self._try_to_find_odoo_template()

        if not template:
            # Try to find Odoo template using information about external variants
            template = self._try_to_find_odoo_template_by_childs()

        if self.env.context.get('skip_mapping_update'):
            return template

        if template:
            self._try_to_update_mappings(template)

        return template

    def _self_validation(self):
        """
        It's very important that the `self` record and it's childs (external_product_variant_ids)
        have to be up-to-date with actual values of `external_reference` and `external_barcode`.
        """
        self.ensure_one()

        external_variants = self.external_product_variant_ids.filtered(  # TODO: Have to be the `child_ids` property
            lambda x: x.code != self.get_one_variant_code()
        )

        if not self.external_reference and not external_variants:
            raise es.ApiImportError(_(
                'External reference is missing for the product template with code "%s" (%s). '
                'Please ensure that the product template has a valid external reference.'
            ) % (self.code, self.name))

        if external_variants:
            references = [x.external_reference for x in external_variants]

            # Case 1: Missing external references for some product variants
            if not all(references):
                raise es.ApiImportError(_(
                    'Some product variants of the product template "%s" (%s) are missing the external reference. '
                    'Please ensure that all product variants have valid external references. '
                    'Affected variants: %s'
                ) % (self.code, self.name, external_variants.format_recordset()))

            # Case 2: Duplicated external references for product variants
            if len(references) != len(set(references)):
                raise es.ApiImportError(_(
                    'Some product variants of the product template "%s" (%s) have duplicated external references. '
                    'Please ensure that all product variants have unique external references. '
                    'Affected variants: %s'
                ) % (self.code, self.name, external_variants.format_recordset()))

            # Case 3: Barcode validation for variants
            if self.integration_id.is_barcode_validation_required():
                variant_barcodes = [x.external_barcode for x in external_variants]

                # Case 3a: Some product variants are missing barcodes
                if any(variant_barcodes) and not all(variant_barcodes):
                    raise es.ApiImportError(_(
                        'Some product variants of the product template "%s" (%s) are missing barcodes. '
                        'Either all variants of the same product should have barcodes, or none of them should '
                        'have barcodes in the external E-Commerce system. Please review the barcode configuration. '
                        'Affected variants: %s'
                    ) % (self.code, self.name, external_variants.format_recordset()))

        return True

    def _try_to_find_odoo_template(self):
        template = self.odoo_record

        # 0. Return the existing mapping
        if template:
            return template

        # Search by the reference
        if self.external_reference:
            template = self._find_product_by_field(
                self._odoo_model,
                self.integration_id.product_reference_name,
                self.external_reference,
            )

            if template:
                return template

        # Search by the barcode
        if self.external_barcode and self.integration_id.is_barcode_validation_required():
            template = self._find_product_by_field(
                self._odoo_model,
                self.integration_id.product_barcode_name,
                self.external_barcode,
            )

        return template

    def _try_to_find_odoo_template_by_childs(self):
        if not self.is_configurable:  # --> child_ids == []
            # 0. If there are no real variants (exclude `complex-zero` code).
            # No way to make mapping successfully --> return empty template
            return self.env['product.template']

        reference_template_dict = dict()

        for external_variant in self.child_ids:
            product = external_variant._search_suitable_variant()
            reference_template_dict[external_variant] = (product.product_tmpl_id.id, product.id)

        # 1. If all found variants point to the same template --> here it is the Template!
        template_ids = [template_id for template_id, __ in reference_template_dict.values()]

        if all(template_ids) and len(set(template_ids)) == 1:
            return self.env['product.template'].browse(set(template_ids))

        # 2. If there are no any variant matches --> return empty template
        if not any(variant_id for __, variant_id in reference_template_dict.values()):
            return self.env['product.template']

        # 3. Serialize partial matches into a detailed error message
        error_message = _(
            '\nERROR! Variants from the same product in the E-Commerce System were mapped '
            'to different product templates in Odoo. Please review the details below and resolve '
            'the issue either in Odoo or on the e-commerce system side:\n'
        )

        for external_variant, (template_id, __) in reference_template_dict.items():
            if template_id:
                error_message += _(
                    'External product "%s" was mapped to the Odoo product template "%s" (ID: %s)\n'
                ) % (
                    external_variant.format_recordset(),
                    self.env['product.template'].browse(template_id).name,
                    template_id,
                )
            else:
                error_message += _(
                    'External product "%s" was not mapped to any Odoo product template\n'
                ) % external_variant.format_recordset()

        raise es.ApiImportError(error_message)

    def _try_to_update_mappings(self, template):
        # Count of the found template's variants is equal to the count of external records.
        # What was checked during searching in the `_find_product_by_field` method.
        # If the template is archived its variants are also archived, so active_test=False
        # is required to find them.
        # WARNING: active_test=False also exposes variants that Odoo archived due to attribute
        # changes (e.g. a value was removed from an attribute line while the variant was used in
        # orders/invoices, so Odoo archived rather than deleted it). Those "deprecated" variants
        # are not valid combinations any more and must not be mapped. This is only safe here
        # because we apply it conditionally (archived template only) and the count assertion below
        # will catch any mismatch between external and Odoo variant counts.
        if not template.active:
            template = template.with_context(active_test=False)
        odoo_variant_ids = template.product_variant_ids
        external_variant_ids = self.external_product_variant_ids

        assert len(odoo_variant_ids) == len(external_variant_ids), _(
            'External mappings count = %s (%s); Odoo variants count = %s (%s)'
        ) % (
            len(external_variant_ids),
            external_variant_ids.format_recordset(),
            len(odoo_variant_ids),
            template,
        )

        # 1. Simple case. Template with the single variant
        if len(external_variant_ids) == 1:
            # TODO: Some of the odoo variants may have excluded from synchronization attributes
            assert len(odoo_variant_ids) < 2, _(
                'External template without variants may not be mapped '
                'to configurable Odoo template: %s → %s [%s]'
            ) % (external_variant_ids.format_recordset(), template, odoo_variant_ids)

            self.create_or_update_mapping(odoo_id=template.id)
            external_variant_ids.create_or_update_mapping(odoo_id=odoo_variant_ids.id)

            return template

        # 2. Multiple variants
        for external_variant in external_variant_ids:
            # Firstly let's unmap current external variant
            external_variant._unmap()

            variant = external_variant._find_suitable_variant(odoo_variant_ids)

            if not variant:
                odoo_variant_info = '\n'.join(
                    f'ID: {v.id}, '
                    f'Internal Reference: {v.default_code or "-"}, '
                    f'Barcode: {v.barcode or "-"}'
                    for v in odoo_variant_ids
                )
                raise es.ApiImportError(_(
                    'The external variant "%s" was not found among the following Odoo records:\n%s.\n\n'
                    'Please make sure that your have corresponding product variant in Odoo. '
                    'If the issue persists, contact our support team for further '
                    'investigation: https://support.ventor.tech/'
                ) % (external_variant.format_recordset(), odoo_variant_info))

            external_variant.create_or_update_mapping(odoo_id=variant.id)

        self.create_or_update_mapping(odoo_id=template.id)

        return template

    def _find_product_by_field(self, model_name, field_name, value):
        """
        :model_name:
            - product.product
            - product.template
        """
        klass = self.env[model_name]

        domain = [
            ('company_id', 'in', [self.integration_id.company_id.id, False]),
            (field_name, '=ilike', escape_psql(value)),
        ]

        product = klass.search(domain, limit=2)

        if len(product) > 1:
            raise es.ApiImportError(_(
                'Multiple %ss were found with the field "%s" (%s) equal to "%s". '
                'Please ensure that the field value is unique to avoid conflicts.'
            ) % (klass._description, klass._get_field_string(field_name), field_name, value))

        if not (product and (model_name == 'product.product')):
            return product

        # If we have found product variant, then it is mandatory to check that all
        # it's variants are having non-empty value in the field that we are using for searching
        # as if not, we have chances that we will not be able to do auto-mapping properly
        template = product.product_tmpl_id

        if len(template.product_variant_ids) != len(self.external_product_variant_ids):
            raise es.ApiImportError(
                _(
                    'The number of product variants for the product template "%s" (ID: %s) is %s, '
                    'but the number of received external records is %s. This mismatch needs to be resolved. \n'
                    'External records: %s'
                ) % (
                    template.name,
                    template.id,
                    len(template.product_variant_ids),
                    len(self.external_product_variant_ids),
                    self.external_product_variant_ids.format_recordset(),
                )
            )

        for variant in template.product_variant_ids:
            if not getattr(variant, field_name):
                raise es.ApiImportError(
                    _(
                        'Some product variants for the product template "%s" (ID: %s) have an '
                        'empty "%s" field (%s = %s). '
                        'Because of this, it is not possible to automatically map the records. Please ensure '
                        'that all variants have a value for this field.'
                    ) % (
                        template.name,
                        template.id,
                        klass._get_field_string(field_name),
                        field_name,
                        value,
                    )
                )

        return product

    def _create_boms(self, template, component_list):
        existing_kit_lines, incoming_kit_lines = [], []

        # 1. Serialize incoming boms
        integration = self.integration_id
        for component in component_list:
            assert ('product_id' in component), _('Product complex-ID missed.')

            odoo_variant = integration._try_get_odoo_product(component, force_create=True)

            incoming_kit_lines.append(
                (
                    ('product_id', odoo_variant.id),
                    ('product_qty', int(component['quantity'])),
                )
            )

        # 2. Serialize existing boms
        kits = template.get_integration_kits(self.integration_id.id, limit=None)

        kit = None
        for record in kits:
            kit_lines = record.bom_line_ids

            if not kit_lines:
                continue

            for line in kit_lines:
                existing_kit_lines.append(
                    (
                        ('product_id', line.product_id.id),
                        ('product_qty', int(line.product_qty)),
                    )
                )

            # 3. Compare incoming and existing kit. Return it if they are fully similar
            if len(kit_lines) == len(incoming_kit_lines):
                if set(incoming_kit_lines) == set(existing_kit_lines):
                    kit = record
                    break

            # 4. Drop existing kit and create the new one. May raise constraint `_ensure_bom_is_free`
            try:
                record.toggle_active()
            except (UserError, ValidationError) as ex:
                _logger.warning(
                    '%s: External product import [%s]. Cannot deactivate the "%s" kit → %s',
                    self.integration_id.name,
                    self.format_recordset(),
                    record,
                    ex.args[0],
                )

        if kit:
            kit.sequence = 0
        else:
            kit = self.env['mrp.bom'].create({
                'sequence': 0,
                'type': 'phantom',
                'product_tmpl_id': template.id,
                'bom_line_ids': [(0, 0, dict(x)) for x in incoming_kit_lines],
                'company_id': template.company_id.id,
            })

        # Recalculate sequence to ensure the new kit will be the first
        for idx, record in enumerate(kits - kit, start=1):
            record.sequence = idx

        return kit

    def _post_import_external_one(self, adapter_external_record):
        self.external_barcode = adapter_external_record['barcode']

    def _create_default_external_variant(self):
        # 1. Drop the all deprecated mapping except default one (code like `100-0`)
        self.child_ids.unlink()

        # Create or update the default variant ext
        return self.external_product_variant_ids.create_or_update({
            'name': self.name,
            'code': self.get_one_variant_code(),
            'external_reference': self.external_reference,
            'external_barcode': self.external_barcode,
            'integration_id': self.integration_id.id,
        })

    def _mark_image_mappings_as_pending(self):
        return self.all_image_mapping_ids.mark_pending()

    def _unlink_image_mappings_pending(self):
        self.all_image_mapping_ids.filtered(lambda x: x.in_pending).unlink()
        self.all_image_external_ids.filtered(lambda x: not x.mapping_ids).unlink()
        return True

    def calculate_import_fields_data(self):
        self.ensure_one()

        integration = self.integration_id
        template_data, *__ = integration.adapter.get_product_for_import(self.code)

        product_template = self.odoo_record

        return product_template \
            .with_context(integration_first_time_import=(not product_template)) \
            .calculate_import_fields_data(integration.id, template_data)

    def action_open_external_product(self):
        """
        Open the product in the e-commerce system.
        """
        self.ensure_one()

        if not self.code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No external product code found.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            url = self.integration_id.get_product_url(self.code)
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        except Exception as e:
            _logger.warning('Failed to get product URL: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Unable to open product in e-commerce system: {str(e)}',
                    'type': 'warning',
                    'sticky': False,
                }
            }
