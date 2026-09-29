# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ExternalOrderRefundLine(models.Model):
    _name = 'external.order.refund.line'
    _description = 'External Order Refund Line'

    refund_id = fields.Many2one(
        comodel_name='external.order.refund',
        string='Refund',
        ondelete='cascade',
        required=True,
    )
    external_line_str_id = fields.Char(
        string='Source Line ID',
        help='Source line ID (lineItem.id)',
    )
    quantity = fields.Float(
        string='Quantity',
    )
    restock_type = fields.Selection(
        selection=[
            ('no_restock', 'No Restock'),
            ('return', 'Return'),
            ('cancel', 'Cancel'),
            ('legacy_restock', 'Legacy Restock'),
        ],
        string='Restock Type',
    )
    external_location_str_id = fields.Char(
        string='External Location ID',
        help='From location.id (restock location)',
    )
    original_unit_price = fields.Monetary(
        string='Original Unit Price',
        currency_field='currency_id',
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        currency_field='currency_id',
        help='After line-level discount allocation',
    )
    total_tax = fields.Monetary(
        string='Total Tax',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
    )
    external_sku = fields.Char(
        string='External SKU',
    )
    is_shipping = fields.Boolean(
        string='Is Shipping',
        default=False,
        help='True when this refund line represents a shipping / delivery fee refund. '
             'Such lines are matched to the credit note delivery line (by the is_delivery '
             'flag on the originating sale order line), not to a product by external id.',
    )
    discount_for_refund = fields.Monetary(
        string='Discount for Refund',
        currency_field='currency_id',
        compute='_compute_discount_for_refund',
        store=True,
        help='original_unit_price * quantity - subtotal',
    )

    @api.depends('original_unit_price', 'quantity', 'subtotal')
    def _compute_discount_for_refund(self):
        for rec in self:
            rec.discount_for_refund = rec.original_unit_price * rec.quantity - rec.subtotal
