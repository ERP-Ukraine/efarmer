# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    product_function_id = fields.Many2one(
        comodel_name="product.function",
        default_model="product.function",
        string="Default Product Function",
        config_parameter="product_function.product_function_id",
    )

    enable_so_tax_auto_calc = fields.Boolean(
        related="company_id.enable_so_tax_auto_calc",
        readonly=False,
    )
