# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    whitelist_history_ids = fields.One2many(
        comodel_name="whitelist.history",
        inverse_name="account_id",
        string="White Lists"
    )
