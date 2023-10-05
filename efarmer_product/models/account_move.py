# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='VAT ID',
        compute='_compute_account_move_product_vat'
    )

    def _compute_account_move_product_vat(self):
        for move in self:
            if move.invoice_line_ids and move.invoice_line_ids.sale_line_ids:
                move.product_vat_id = move.invoice_line_ids.sale_line_ids[0].order_id.product_vat_id
