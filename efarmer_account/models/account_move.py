# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
        check_company=True,
        copy=False,
    )
    posted_uid = fields.Many2one(
        "res.users", string="Posted by", readonly=True, copy=False
    )

    def action_post(self):
        res = super().action_post()

        for move in self:
            # Capture posting user
            if move.state == "posted":
                move.posted_uid = self.env.user.id

        return res
