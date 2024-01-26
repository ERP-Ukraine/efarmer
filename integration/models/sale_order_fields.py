# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrderFields(models.Model):
    _name = 'sale.order.fields'
    _description = 'Sale Order Fields'

    order_id = fields.Many2one(
        'sale.order',
        string='Order Reference',
    )
    name = fields.Char(
        string='System Name',
        size=512,
    )
    label = fields.Char(
        string='Label',
        size=512,
    )
    value = fields.Text(
        string='Value',
    )
