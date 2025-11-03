# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
        check_company=True,
        copy=False,
    )
