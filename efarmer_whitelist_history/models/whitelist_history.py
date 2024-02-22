# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class WhiteListHistory(models.Model):
    _name = 'whitelist.history'
    _description = 'WhiteList History'
    _order = 'id desc'

    name = fields.Char(string='Name', copy=False)
    token = fields.Char(string='Token')
    invoice_number = fields.Char(string='Reference Number')
    account_id = fields.Many2one(comodel_name='account.move', string='Reference')
    partner_id = fields.Many2one(related='account_id.partner_id', store=True)
    message = fields.Char(string='Message')
    partner_bank_acc = fields.Char(
        related='account_id.partner_bank_id.sanitized_acc_number',
        string='Partner Bank Account'
    )
