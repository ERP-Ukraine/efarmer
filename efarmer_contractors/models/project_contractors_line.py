# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class ProjectContractorsLine(models.Model):
    _name = 'project.contractors.line'
    _description = 'Project Contractors Line'

    # account_asset_counterpart_id = fields.Many2one(
    #     'account.account',
    #     string='Account Asset Counterpart',
    # )
    hours_spent = fields.Float(string='Hours Spent')
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    contractors_id = fields.Many2one(
        'project.contractors',
        string='Contractors',
    )

    analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string='Analytic Line',
    )
    asset_analytic_line = fields.Many2one(
        related='analytic_line_id.task_product_id',
        string='Asset Analytic Line',
    )
    employee_id = fields.Many2one(comodel_name='hr.employee')
    pay_rate = fields.Float(
        string='Pay Rate',
        related='employee_id.pay_rate',
        store=True,
    )
    description = fields.Char(string='Description')

    # asset_id = fields.Many2one(
    #     comodel_name='account.asset',
    #     string='Product',
    # )

