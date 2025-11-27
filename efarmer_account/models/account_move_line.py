# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move.line"

    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
        related='move_id.department_id',
        store=True,
        readonly=True,
    )
