# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

RESTRICT_GROUP = "efarmer_account.group_cancel_posted_customer_invoice"


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

    restrict_customer_invoice_cancel = fields.Boolean(
        compute="_compute_restrict_customer_invoice_cancel",
        help="True when the current user may not reset to draft "
             "or cancel this (previously posted) customer invoice.",
    )

    def action_post(self):
        res = super().action_post()

        for move in self:
            # Capture posting user
            if move.state == "posted":
                move.posted_uid = self.env.user.id

        return res

    def _is_protected_customer_invoice(self):
        """Customer invoice that has been posted"""
        self.ensure_one()
        return self.move_type == "out_invoice" and (
            self.posted_before or self.state == "posted"
        )

    def _can_reset_cancel_posted_customer_invoices(self):
        # Superuser mode is not restricted.
        return self.env.su or self.env.user.has_group(RESTRICT_GROUP)

    def _check_customer_invoice_reset_cancel_rights(self):
        if self._can_reset_cancel_posted_customer_invoices():
            return
        if any(move._is_protected_customer_invoice() for move in self):
            raise AccessError(_(
                "You do not have permission to reset posted customer "
                "invoices to draft or cancel them."
            ))

    @api.depends("move_type", "state", "posted_before")
    @api.depends_context("uid")
    def _compute_restrict_customer_invoice_cancel(self):
        allowed = self._can_reset_cancel_posted_customer_invoices()
        for move in self:
            move.restrict_customer_invoice_cancel = (
                not allowed and move._is_protected_customer_invoice()
            )

    def button_draft(self):
        self._check_customer_invoice_reset_cancel_rights()
        return super().button_draft()

    def button_cancel(self):
        self._check_customer_invoice_reset_cancel_rights()
        return super().button_cancel()

    def write(self, vals):
        if not self._can_reset_cancel_posted_customer_invoices():
            to_check = self.browse()
            new_state = vals.get("state")
            if new_state in ("draft", "cancel"):
                to_check |= self.filtered(lambda m: m.state != new_state)
            if "posted_before" in vals and not vals["posted_before"]:
                # Clearing the flag would bypass the "ever posted" rule.
                to_check |= self
            to_check._check_customer_invoice_reset_cancel_rights()
        return super().write(vals)
