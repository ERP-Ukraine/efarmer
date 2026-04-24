# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_func_id = fields.Many2one(
        comodel_name="product.function",
        string="Product Function",
    )
    bom_type = fields.Selection(
        related="bom_ids.type",
        string="BoM Type",
        store=True,
    )
