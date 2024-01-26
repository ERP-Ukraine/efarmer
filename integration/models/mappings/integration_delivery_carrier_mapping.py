# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationDeliveryCarrierMapping(models.Model):
    _name = 'integration.delivery.carrier.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Delivery Carrier Mapping'
    _mapping_fields = ('carrier_id', 'external_carrier_id')

    carrier_id = fields.Many2one(
        comodel_name='delivery.carrier',
        ondelete='set null',
    )

    external_carrier_id = fields.Many2one(
        comodel_name='integration.delivery.carrier.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_carrier_id)',
            'Delivery Carrier mapping should be unique per integration'
        ),
    ]

    def _fix_unmapped_shipping_multi(self):
        results = list()
        for rec in self:
            result = rec._fix_unmapped_shipping_one()
            results.append(result)
        return results

    def _fix_unmapped_shipping_one(self):
        self.ensure_one()
        self._fix_unmapped_by_search()

        carrier_id = self.carrier_id
        if carrier_id or not self.external_carrier_id:
            return carrier_id

        if not self.integration_id.auto_create_delivery_carrier_on_so:
            return False

        ref_field = self.integration_id._get_product_reference_name()

        product_vals = {
            'type': 'service',
            'sale_ok': False,
            'purchase_ok': False,
            'list_price': float(),
            'integration_ids': [(5, 0, 0)],
            'name': self.external_carrier_id.name,
            ref_field: self.external_carrier_id.code,
            'categ_id': self.env.ref('delivery.product_category_deliveries').id,
        }

        product_template = self.env['product.template']\
            .with_context(skip_product_export=True).create(product_vals)
        product_variant = product_template.product_variant_ids

        assert len(product_variant) == 1, 'Expected single product variant'

        carrier_vals = {
            'name': product_variant.name,
            'product_id': product_variant.id,
        }
        odoo_carrier = carrier_id.create(carrier_vals)

        self.carrier_id = odoo_carrier.id

        return odoo_carrier

    def _fix_unmapped_by_search(self):
        carrier_id = self.carrier_id
        if carrier_id or not self.external_carrier_id:
            return carrier_id

        ref_field = self.integration_id._get_product_reference_name()
        product_template = self.env['product.template'].search([
            ('name', '=', self.external_carrier_id.name),
            (ref_field, '=', self.external_carrier_id.code),
        ])
        if not product_template:
            return carrier_id

        odoo_carrier = carrier_id.search([
            ('name', '=', self.external_carrier_id.name),
            ('product_id', 'in', product_template.mapped('product_variant_ids.id')),
        ], limit=1)

        if odoo_carrier:
            self.carrier_id = odoo_carrier.id

        return odoo_carrier
