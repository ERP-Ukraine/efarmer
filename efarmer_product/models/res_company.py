# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_so_tax_auto_calc = fields.Boolean(
        string="Enable Auto-calculate taxes on Sales Orders",
        default=False,
    )
