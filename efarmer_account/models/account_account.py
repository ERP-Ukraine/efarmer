# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    allow_payable_transfer = fields.Boolean(string='Allow Transfer from Payable', default=False, tracking=True,
        help="If checked, this account will be treated like a payable account "
        "when calculating the Residual Amount in purchase orders."
    )
