# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_func_id = fields.Many2one(
        comodel_name='product.function',
        string='Product Function',
    )
