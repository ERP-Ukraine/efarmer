# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class ProjectCapitalizationLine(models.Model):
    _name = "project.capitalization.line"
    _description = "Project Capitalization Line"

    account_asset_counterpart_id = fields.Many2one(
        "account.account",
        string="Account Asset Counterpart",
    )
    hours_spent = fields.Float(string="Hours Spent")
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    capitalization_id = fields.Many2one(
        "project.capitalization",
        string="Capitalization",
    )
    analytic_line_id = fields.Many2one(
        "account.analytic.line",
        string="Analytic Line",
    )
    asset_analytic_line = fields.Many2one(
        related="analytic_line_id.task_product_id",
        string="Asset Analytic Line",
    )
    asset_id = fields.Many2one(
        comodel_name="account.asset",
        string="Product",
    )
