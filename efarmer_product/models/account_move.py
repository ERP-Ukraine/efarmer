# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='Product Vat',
    )
