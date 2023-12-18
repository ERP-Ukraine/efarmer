# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class WhiteListHistory(models.Model):
    _name = 'whitelist.history'
    _description = 'WhiteList History'

    name = fields.Char(string='Name', copy=False)
    token = fields.Char(string='Token')
    invoice_number = fields.Char(string='Invoice Number')
    account_id = fields.Many2one(comodel_name="account.move", string="Account Move ID")
    message = fields.Char(string='Message')
    invoice_partner_bank_acc = fields.Char(
        related='account_id.partner_bank_id.sanitized_acc_number',
        string='Partner Bank Account'
    )
