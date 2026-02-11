from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    name = fields.Char(translate=True)
