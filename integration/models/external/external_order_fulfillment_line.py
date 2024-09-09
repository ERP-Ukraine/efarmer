# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderFulfillmentLine(models.Model):
    _name = 'external.order.fulfillment.line'
    _description = 'External Order Fulfillment Line'

    external_str_id = fields.Char(
        string='External ID',
    )
    code = fields.Char(
        string='Code',
    )
    external_reference = fields.Char(
        string='Product Reference',
    )
    quantity = fields.Integer(
        string='Fulfilled',
    )
    fulfillable_quantity = fields.Integer(
        string='Pending Quantity',
        help='Pending fulfillment in the future',
    )
    fulfillment_id = fields.Many2one(
        comodel_name='external.order.fulfillment',
        string='Fulfillment ID',
        ondelete='cascade',
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.external_reference}: {rec.quantity}'
