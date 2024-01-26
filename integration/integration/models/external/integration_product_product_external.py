# See LICENSE file for full copyright and licensing details.

import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IntegrationProductProductExternal(models.Model):
    _name = 'integration.product.product.external'
    _inherit = ['integration.external.mixin', 'integration.product.external.mixin']
    _description = 'Integration Product Product External'
    _odoo_model = 'product.product'

    external_barcode = fields.Char(
        string='Barcode',
    )

    external_product_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Product Template',
        readonly=True,
        ondelete='cascade',
    )

    external_attribute_value_ids = fields.Many2many(
        comodel_name='integration.product.attribute.value.external',
        relation='external_product_attribute_value_rel',
        column1='external_product_id',
        column2='external_attribute_value_id',
        string='External Attribute Values',
    )

    def apply_stock_levels(self, qty, location):
        self.ensure_one()

        variant = self.mapping_model.to_odoo(
            integration=self.integration_id,
            code=self.code,
        )

        if variant.type != 'product' or variant.tracking != 'none':
            return variant, location, False

        StockQuant = self.env['stock.quant'].with_context(skip_inventory_export=True)

        # Set stock levels to zero
        inventory_locations = self.env['stock.location'].search([
            ('parent_path', 'like', location.parent_path + '%'),
            ('id', '!=', location.id)
        ])

        inventory_quants = StockQuant.search([
            ('location_id', 'in', inventory_locations.ids),
            ('product_id', '=', variant.id),
        ])

        inventory_quants.inventory_quantity = 0
        inventory_quants.action_apply_inventory()

        # Set new stock level
        inventory_quant = StockQuant.search([
            ('location_id', '=', location.id),
            ('product_id', '=', variant.id),
        ])

        if not inventory_quant:
            inventory_quant = StockQuant.create({
                'location_id': location.id,
                'product_id': variant.id,
            })

        float_qty = float(qty or False)
        inventory_quant.inventory_quantity = float_qty
        inventory_quant.action_apply_inventory()
        return variant, location, float_qty

    def _fix_unmapped(self, adapter_external_data):
        # We can't use this method, because products are imported by blocks
        pass

    def _post_import_external_one(self, adapter_external_record):
        """
        This method will receive individual variant record.
        And link external variant with external template.
        """
        template_code = adapter_external_record.get('ext_product_template_id')
        if not template_code:
            raise UserError(
                _('External Product Variant should have "ext_product_template_id" field')
            )

        external_template = self.env['integration.product.template.external'].search([
            ('code', '=', template_code),
            ('integration_id', '=', self.integration_id.id),
        ])

        if not external_template:
            raise UserError(
                _('No External Product Template found with code %s. '
                  'Maybe templates are not exported yet?') % template_code
            )

        assert len(external_template) == 1  # just to doublecheck, as it should never happen

        self.write({
            'external_barcode': adapter_external_record['barcode'],
            'external_product_template_id': external_template.id,
        })

    @api.model
    def create_or_update(self, vals):
        if 'deprecated_code' in vals:
            # During product export `code` may be kind of `deprecated` (70-0 --> 70-71)
            # if we changed number of variants. We need to do the search of the external record
            # by old the value and than update it by the new value.
            vals['code'] = vals.pop('deprecated_code')

        return super().create_or_update(vals)

    def format_recordset(self):
        return str(
            self.mapped(
                lambda x: (f'<id={x.id}>', x.code, x.external_reference, x.external_barcode)
            )
        )

    def _search_suitable_variant(self):
        self.ensure_one()

        # Search by the reference
        product = self.external_product_template_id._find_product_by_field(
            self._odoo_model,
            self.integration_id._get_product_reference_name(),
            self.external_reference,
        )

        # Search by the barcode
        if not product and self.external_barcode and self.integration_id._need_for_barcode():
            product = self.external_product_template_id._find_product_by_field(
                self._odoo_model,
                self.integration_id._get_product_barcode_name(),
                self.external_barcode,
            )

        return product

    def _find_suitable_variant(self, odoo_variant_ids):
        # 1. Map by reference
        variant = self._filter_variants_by_reference(odoo_variant_ids)

        # 2. Map by barcode
        if not variant:
            variant = self._filter_variants_by_barcode(odoo_variant_ids)

        # 3. Map by attributes
        if not variant:
            variant = self._filter_variants_by_attrs(odoo_variant_ids)

        return variant or self.env[self._odoo_model]

    def _filter_variants_by_reference(self, odoo_records):
        reference_field = self.integration_id._get_product_reference_name()
        router = {getattr(x, reference_field): x for x in odoo_records}
        return router.get(self.external_reference)

    def _filter_variants_by_barcode(self, odoo_records):
        barcode_field = self.integration_id._get_product_barcode_name()
        router = {getattr(x, barcode_field): x for x in odoo_records}
        return router.get(self.external_reference)

    def _filter_variants_by_attrs(self, odoo_records):
        attribute_value_ids = self.env['product.attribute.value']
        for external_value in self.external_attribute_value_ids:
            attribute_value_ids += external_value.odoo_record\
                .filtered(lambda x: not x.exclude_from_synchronization)

        result = list()

        for record in odoo_records:
            record_value_ids = record.product_template_attribute_value_ids\
                .mapped('product_attribute_value_id')\
                .filtered(lambda x: not x.exclude_from_synchronization)

            if (record_value_ids == attribute_value_ids):
                result.append(record)

        return result[0] if result else None

    def _create_internal_import_line(self):
        res = super()._create_internal_import_line()

        res.write({
            'origin_parent_id': self.external_product_template_id.id,
            'attribute_list': str(self.external_attribute_value_ids.mapped('code')),
        })

        return res

    def _update_variant_media(self, product, image_data):
        if not image_data['images']:
            return

        image_list = image_data['variants'].get(self.code, [])
        if not image_list:
            return

        # Update variant images only if variants more than 1
        if len(product.product_tmpl_id.product_variant_ids) < 2:
            return

        ext_img_id = image_list[0]
        img_data = image_data['images'].get(ext_img_id)

        if img_data and not self.verify_image_data(product, img_data):
            ext_img_id = False
            img_data = False

        if img_data:
            product.image_1920 = base64.b64encode(img_data)

        product.update_mapping_any(self.integration_id, 'image_variant_1920', 'image', ext_img_id)

    def create_or_update_mapping(self, odoo_id=None):
        mapping = super().create_or_update_mapping(odoo_id=odoo_id)

        if odoo_id is not None:
            # (3, id, 0) - removes the record of <id> from the set, but does not delete it.
            # (4, id, 0) - adds an existing record of <id> to the set.
            mapping.odoo_record.with_context(skip_product_export=True)\
                .write(dict(integration_ids=[((4 if odoo_id else 3), self.integration_id.id, 0)]))

        return mapping
