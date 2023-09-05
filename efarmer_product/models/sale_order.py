# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='Product Vat',
    )

    @api.onchange('order_line')
    def _onchange_line_tax_id(self):
        self.order_line._compute_tax_id()
