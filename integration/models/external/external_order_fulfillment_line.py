# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderFulfillmentLine(models.Model):
    _name = 'external.order.fulfillment.line'
    _description = 'Fulfilled Order Item'

    external_str_id = fields.Char(
        string='External Item ID',
        help='Unique identifier for this item in the external system',
    )
    code = fields.Char(
        string='Product Code',
        help='Internal product code or SKU',
    )
    external_reference = fields.Char(
        string='Product Reference',
        help='Product identifier from the external e-commerce system',
    )
    quantity = fields.Integer(
        string='Quantity Fulfilled',
        help='Number of units shipped in this fulfillment',
    )
    fulfillable_quantity = fields.Integer(
        string='Remaining Quantity',
        help='Quantity still pending fulfillment for this order item',
    )
    fulfillment_id = fields.Many2one(
        comodel_name='external.order.fulfillment',
        string='Fulfillment',
        ondelete='cascade',
        help='Parent fulfillment record',
    )

    def _compute_display_name(self):
        """Generate a user-friendly display name for the fulfillment line"""
        for rec in self:
            rec.display_name = f'{rec.external_reference}: {rec.quantity} units'
