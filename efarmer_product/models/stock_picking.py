# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        related='sale_id.product_vat_id',
        string='VAT ID',
    )
