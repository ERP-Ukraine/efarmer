# See LICENSE file for full copyright and licensing details.

import base64
import logging

from odoo import models, fields, _
from odoo.exceptions import ValidationError
from odoo.tools.sql import escape_psql

from ...tools import IS_FALSE
from ...exceptions import ApiImportError


_logger = logging.getLogger(__name__)


class IntegrationProductTemplateExternal(models.Model):
    _name = 'integration.product.template.external'
    _inherit = ['integration.external.mixin', 'integration.product.external.mixin']
    _description = 'Integration Product Template External'
    _odoo_model = 'product.template'

    external_barcode = fields.Char(
        string='Barcode',
    )

    external_product_variant_ids = fields.One2many(
        comodel_name='integration.product.product.external',
        inverse_name='external_product_template_id',
        string='External Product Variants',
        readonly=True,
    )

    @property
    def one_variant_code(self):
        return f'{self.code}-{IS_FALSE}'

    @property
    def child_ids(self):
        return self.external_product_variant_ids.filtered(
            lambda x: x.code != self.one_variant_code
        )

    @property
    def is_configurable(self):
        return bool(self.child_ids)

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

    def run_import_products(self, import_images=False, trigger_export_other=False):
        for external_template in self:
            integration = external_template.integration_id
            integration = integration.with_context(company_id=integration.company_id.id)

            job_kwargs = integration._job_kwargs_import_product(external_template)
            job = integration.with_delay(**job_kwargs).import_product(
                external_template.id,
                import_images=import_images,
                trigger_export_other=trigger_export_other,
            )
            external_template.job_log(job)

        plural = ('', 'is') if len(self) == 1 else ('s', 'are')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Product'),
                'message': 'Queue Job%s "Product Import" %s created' % plural,
                'type': 'success',
                'sticky': False,
            }
        }

    def import_one_product(self, template_data, variants_data, bom_data, image_data):
        if bom_data and not self.integration_id.is_installed_mrp:
            raise ValidationError(_(
                'The product contains bom-components,'
                'however the Manufacturing module is not installed.'
            ))

        self = self.with_context(skip_product_export=True)

        import_images = self._context.get('integration_import_images')

        # 1. Try map template and variants
        template = self.with_context(
            skip_mapping_update=True,
            default_operation_mode='import',
        ).try_map_template_and_variants((template_data, variants_data))

        # 2. Update or create template with received data
        if template:
            self._update_template_from_external(template, template_data)
        else:
            template = self.with_context(integration_product_creating=True)\
                ._create_template(template_data)

        # 2.1 Update template images
        if import_images:
            self._update_template_media(template, image_data)

        # 2.2 If no variants-data --> update mapping for the default Odoo variant
        if not variants_data:
            self._try_to_update_mappings(template)

        # 3. Find and update all the variants with received data
        for variant_data in variants_data:
            # 3.1 Init receive-converter
            converter = self.integration_id.init_receive_field_converter(
                self.env['product.product'],
                variant_data,
            )

            # 3.2 Find external record by `complex-code`
            code = converter.get_ext_attr('variant_id')
            external_variant = self.external_product_variant_ids\
                .filtered(lambda x: x.code == code)

            assert external_variant, _('External variant %s not found') % code
            vals = converter.convert_from_external()

            # 3.3 Find suitable variant among template childs.
            variant = external_variant._find_suitable_variant(template.product_variant_ids)

            if not variant:
                # 3.3.1 Create the new variant if Odoo didn't creat it automatically because of
                # the dynamic-attributes and the `integration_product_creating` context variable
                attribute_values = converter._get_template_attribute_values(template.id)

                vals.update(
                    product_tmpl_id=template.id,
                    product_template_attribute_value_ids=[(6, 0, attribute_values.ids)],
                )

            # 3.4 Create / Update variant with actual values
            variant = external_variant.create_or_update_with_translation(
                self.integration_id, variant, vals)

            # 3.5 Link external record to odoo record (make mapping)
            external_variant.create_or_update_mapping(odoo_id=variant.id)

            # 3.6 Update variant images
            if import_images:
                external_variant._update_variant_media(variant, image_data)

        # 4. Handle kit components
        if bom_data:
            self._create_boms(template, bom_data)

        return template

    def _update_template_media(self, template, image_data):
        template.product_template_image_ids.unlink()
        template.image_1920 = False

        if not image_data['images']:
            return

        is_template_image = True
        for ext_img_id, bin_data in image_data['images'].items():
            if not self.verify_image_data(template, bin_data):
                is_template_image = False
                continue

            b64_image = base64.b64encode(bin_data)

            if is_template_image:
                template.image_1920 = b64_image
                template.update_mapping_any(self.integration_id, 'image_1920', 'image', ext_img_id)
                is_template_image = False
            else:
                product_image = self.env['product.image'].create({
                    'name': template.name,
                    'image_1920': b64_image,
                    'product_tmpl_id': template.id,
                })

                template.product_template_image_ids += product_image

    def _update_template_from_external(self, template, ext_data):
        converter = self.integration_id.init_receive_field_converter(template, ext_data)
        attr_values_ids_by_attr_id = converter.get_ext_attr('attr_values_ids_by_attr_id')

        # 1. Update template attributes (actualize variants count)
        for attr_id, value_ids in attr_values_ids_by_attr_id.items():
            existing_line = template.attribute_line_ids\
                .filtered(lambda x: x.attribute_id.id == attr_id)

            if existing_line:
                existing_line.value_ids = [(6, 0, value_ids)]
            else:
                template.attribute_line_ids = [(0, 0, {
                    'attribute_id': attr_id,
                    'value_ids': [(6, 0, value_ids)],
                })]

        # 2. Update template with actual values
        upd_vals = converter.convert_from_external()

        template = self.create_or_update_with_translation(
            integration=self.integration_id,
            odoo_object=template,
            vals=upd_vals,
        )

        return template

    def _create_template(self, ext_template):
        converter = self.integration_id.init_receive_field_converter(
            self.env['product.template'],
            ext_template,
        )
        upd_vals = converter.convert_from_external()
        attr_values_ids_by_attr_id = converter.get_ext_attr('attr_values_ids_by_attr_id')

        attribute_line_ids = [
            (0, 0, {
                'attribute_id': attr_id,
                'value_ids': [(6, 0, value_ids)],
            }) for attr_id, value_ids in attr_values_ids_by_attr_id.items()
        ]
        if attribute_line_ids:
            upd_vals['attribute_line_ids'] = attribute_line_ids

        template = self.create_or_update_with_translation(
            integration=self.integration_id,
            odoo_object=self.env['product.template'],
            vals=upd_vals,
        )

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

        external_variants = self.child_ids

        if not self.external_reference and not external_variants:
            raise ApiImportError(
                _('Reference is empty for the product (%s) %s') % (self.code, self.name)
            )

        if external_variants:
            references = [x.external_reference for x in external_variants]

            if not all(references):
                raise ApiImportError(
                    _(
                        'Reference field is empty for some product variants '
                        'of the product: (%s) %s --> Externals: %s'
                    ) % (
                        self.code,
                        self.name,
                        external_variants.format_recordset(),
                    )
                )

            if len(references) != len(set(references)):
                raise ApiImportError(
                    _(
                        'Reference field is duplicated for some product variants '
                        'of the product: (%s) %s --> Externals: %s'
                    ) % (
                        self.code,
                        self.name,
                        external_variants.format_recordset(),
                    )
                )

            if self.integration_id._need_for_barcode():
                variant_barcodes = [x.external_barcode for x in external_variants]

                if any(variant_barcodes) and not all(variant_barcodes):
                    raise ApiImportError(
                        _('Barcode field is empty for some product variants of the product: (%s) '
                          '%s. Note that either all variants of the same product should have '
                          'barcodes, or all variants of the same product should not have barcodes '
                          'in the external e-Commerce system') % (self.code, self.name)
                    )

        return True

    def _try_to_find_odoo_template(self):
        template = self.odoo_record

        # 0. Return the existing mapping
        if template:
            if not template.active:
                template = template.with_context(active_test=False)
            return template

        # Search by the reference
        if self.external_reference:
            template = self._find_product_by_field(
                self._odoo_model,
                self.integration_id._get_product_reference_name(),
                self.external_reference,
            )

            if template:
                return template

        # Search by the barcode
        if self.external_barcode and self.integration_id._need_for_barcode():
            template = self._find_product_by_field(
                self._odoo_model,
                self.integration_id._get_product_barcode_name(),
                self.external_barcode,
            )

        return template

    def _try_to_find_odoo_template_by_childs(self):
        if not self.is_configurable:  # --> child_ids == []
            # 0. If there are no the real variants (exclude `complex-zero` code).
            # No way to make mapping successfully --> return empty template
            return self.env['product.template']

        reference_template_dict = dict()

        for external_variant in self.child_ids:
            product = external_variant._search_suitable_variant()
            reference_template_dict[external_variant] = (product.product_tmpl_id.id, product.id)

        # 1. If the all found variants point to the same tamplete --> here it is the Template!
        template_ids = [template_id for template_id, __ in reference_template_dict.values()]

        if all(template_ids) and len(set(template_ids)) == 1:
            return self.env['product.template'].browse(set(template_ids))

        # 2. If there are no any variant matches --> return empty template
        if not any(variant_id for __, variant_id in reference_template_dict.values()):
            return self.env['product.template']

        # 3. Serialize partial matches to the verbose error
        error_message = _(
            'ERROR! Variants from the same product in e-Commerce System were mapped '
            'to several different product templates in Odoo. Please, check below '
            'details and fix them either on Odoo on e-Commerce System side:\n'
        )

        for external_variant, (template_id, __) in reference_template_dict.items():
            if template_id:
                error_message += _(
                    'External product "%s" was mapped to Odoo Template with name "%s" and id=%s\n'
                ) % (
                    external_variant.format_recordset(),
                    self.env['product.template'].browse(template_id).name,
                    template_id,
                )
            else:
                error_message += _(
                    'External product "%s" was not mapped to any Odoo Template\n'
                ) % external_variant.format_recordset()

        raise ApiImportError(error_message)

    def _try_to_update_mappings(self, template):
        # Count of the found template's variants is equal to the count of external records.
        # What was checked during searching in the `_find_product_by_field` method.
        odoo_variant_ids = template.product_variant_ids
        external_variant_ids = self.external_product_variant_ids

        assert len(odoo_variant_ids) == len(external_variant_ids), _(
            'External mappings count = %s (%s); Odoo variants count = %s (%s)'
        ) % (
            len(external_variant_ids),
            len(odoo_variant_ids),
            external_variant_ids.format_recordset(),
            template,
        )

        # 1. Simple case. Template with the single variant
        if len(external_variant_ids) == 1:
            # TODO: Some of the odoo variants may have excluded from synchronization attributes
            assert len(odoo_variant_ids) < 2, _(
                'External template without variants may not be mapped '
                'to configurable Odoo template: %s --> %s [%s]'
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
                raise ApiImportError(
                    _('External variant "%s" not found among odoo records %s')
                    % (external_variant.format_recordset(), odoo_variant_ids)
                )

            external_variant.create_or_update_mapping(odoo_id=variant.id)

        self.create_or_update_mapping(odoo_id=template.id)

        return template

    def _find_product_by_field(self, model_name, field_name, value):
        """
        :model_name:
            - prodict.product
            - product.template
        """
        klass = self.env[model_name]
        product = klass.search([(field_name, '=ilike', escape_psql(value))])

        if len(product) > 1:
            raise ApiImportError(
                _(
                    'There are several %ss with the field "%s" (%s) = %s.'
                ) % (klass._description, klass._get_field_string(field_name), field_name, value)
            )

        if not (product and (model_name == 'product.product')):
            return product

        # If we have found product variant, then it is mandatory to check that all
        # it's variants are having non-empty value in the field that we are using for searching
        # as if not, we have chances that we will not be able to do auto-mapping properly
        template = product.product_tmpl_id

        if len(template.product_variant_ids) != len(self.external_product_variant_ids):
            raise ApiImportError(
                _(
                    'Count of Product Variants for the found Product Template "%s" (id=%s) '
                    'is %s and the count of received external records is %s --> Externals: %s'
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
                raise ApiImportError(
                    _(
                        'Not all product variants of the Product Template with name "%s" '
                        '(id=%s) has non-empty field "%s (%s) = %s". Because of this it is not '
                        'possible to automatically guess mapping. Please, fill in above field.'
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
        bom_line_ids = list()
        template.bom_ids.unlink()

        for component in component_list:
            assert ('product_id' in component), _('Product complex-ID missed.')

            odoo_variant = self.env['integration.sale.order.factory']\
                ._try_get_odoo_product(self.integration_id, component, force_create=True)

            bom_line_ids.append(
                (0, 0, dict(product_id=odoo_variant.id, product_qty=component['quantity']))
            )

        return self.env['mrp.bom'].create({
            'type': 'phantom',
            'bom_line_ids': bom_line_ids,
            'product_tmpl_id': template.id,
        })

    def _post_import_external_one(self, adapter_external_record):
        self.external_barcode = adapter_external_record['barcode']

    def _create_default_external_variant(self):
        # 1. Drop the all deprecated mapping except default one (code like `100-0`)
        self.external_product_variant_ids\
            .filtered(lambda x: x.code != self.one_variant_code).unlink()

        # Create or update the default variant ext
        return self.external_product_variant_ids.create_or_update({
            'name': self.name,
            'code': self.one_variant_code,
            'external_reference': self.external_reference,
            'external_barcode': self.external_barcode,
            'integration_id': self.integration_id.id,
        })
