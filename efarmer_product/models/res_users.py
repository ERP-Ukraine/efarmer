# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    disable_so_tax_auto_calc = fields.Boolean(
        string="Disable Auto-calculate taxes on Sales Orders",
        default=False,
    )
