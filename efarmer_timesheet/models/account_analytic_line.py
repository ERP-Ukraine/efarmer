# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    is_capitalized = fields.Boolean(
        string="Capitalized",
        default=False,
    )
    task_product_id = fields.Many2one(
        string='Task asset id',
        related='task_id.asset_id',
        store=True,
    )
    account_asset_counterpart_id = fields.Many2one(
        related="employee_id.account_asset_counterpart_id",
        string='Account Asset Counterpart',
        store=True,
    )
    is_paid = fields.Boolean(
        string="Paid",
        default=False,
    )
    epic_id = fields.Many2one(
        string='Epic Task',
        related='task_id.epic_id',
        store=True,
    )
    name_pl = fields.Char(
        string='Name PL',
        related='task_id.name_pl',
        store=True,
    )
    product_version_id = fields.Many2one(
        string='Product Version',
        related='task_id.product_version_id',
        store=True,
    )
    employee_type = fields.Selection(
        related='employee_id.employee_type',
        string='Employee Type',
        store=True,
    )
    pay_rate = fields.Float(
        string='Pay Rate',
        related='employee_id.pay_rate',
        store=True,
    )
    bamboo_currency_id = fields.Many2one(
        'res.currency',
        string='Pay Rate Currency',
        related='employee_id.bamboo_currency_id',
        store=True,
    )

    # def unlink(self):
    #     for line in self:
    #         if line.is_capitalized:
    #             raise UserError(_('You cannot delete a Capitalized analytic line.'))
    #         if line.is_paid:
    #             raise UserError(_('You cannot delete a Paid analytic line.'))
    #     return super(AccountAnalyticLine, self).unlink()
    #
    # def write(self, vals):
    #     for line in self:
    #         if line.is_capitalized:
    #             raise UserError(_('You cannot edit a Capitalized analytic line.'))
    #         if line.is_paid:
    #             raise UserError(_('You cannot edit a Paid analytic line.'))
    #     return super(AccountAnalyticLine, self).write(vals)
