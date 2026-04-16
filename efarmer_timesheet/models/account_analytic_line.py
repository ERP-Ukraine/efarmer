# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    is_capitalized = fields.Boolean(
        string="Capitalized",
        default=False,
    )
    task_product_id = fields.Many2one(
        string="Task asset id",
        related="task_id.asset_id",
        store=True,
    )
    account_asset_counterpart_id = fields.Many2one(
        related="employee_id.account_asset_counterpart_id",
        string="Account Asset Counterpart",
        store=True,
    )
    is_paid = fields.Boolean(
        string="Paid",
        default=False,
    )
    epic_id = fields.Many2one(
        string="Epic Task",
        related="task_id.epic_id",
        store=True,
    )
    name_pl = fields.Char(
        string="Name PL",
        related="task_id.name_pl",
        store=True,
    )
    product_version_id = fields.Many2one(
        string="Product Version",
        related="task_id.product_version_id",
        store=True,
    )
    issue_type_id = fields.Many2one(
        string="Issue Type",
        related="task_id.issue_type_id",
        store=True,
    )
    employee_type = fields.Selection(
        related="employee_id.employee_type",
        string="Employee Type",
        store=True,
    )
    bamboo_currency_id = fields.Many2one(
        "res.currency",
        string="Pay Rate Currency",
        related="employee_id.bamboo_currency_id",
        store=True,
    )
    capital_labour_cost = fields.Float(
        string="Capitalized Labour Cost",
        compute="_compute_capital_values",
        store=True,
        aggregator="sum",
    )
    capital_unit_amount = fields.Float(
        string="Total Time Capitalized",
        compute="_compute_capital_values",
        store=True,
        aggregator="sum",
    )
    percent_capital_labour_cost = fields.Float(
        string="% Capitalized Labor Cost",
        compute="_compute_capital_values",
        store=True,
    )
    rate_per_hour = fields.Float(
        string="Rate per Hour",
        readonly=True,
        copy=False,
        aggregator="avg",
    )
    amount_eur = fields.Monetary(
        string="Amount, EUR",
        compute="_compute_amount_eur",
        copy=False,
        readonly=True,
        store=True,
        aggregator="sum",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Define rate_per_hour only when creating Timesheet object"""
        for vals in vals_list:
            if "rate_per_hour" not in vals:
                employee = self.env["hr.employee"].browse(
                    vals.get("employee_id", False)
                )
                if employee:
                    vals.update({"rate_per_hour": employee.hourly_cost})
        return super(AccountAnalyticLine, self).create(vals_list)

    @api.depends("amount", "employee_id", "date")
    def _compute_amount_eur(self):
        eur_currency = self.env["res.currency"].search([("name", "=", "EUR")], limit=1)
        for line in self:
            if line.employee_id:
                currency_rate = self.env["res.currency"]._get_conversion_rate(
                    line.employee_id.currency_id,
                    eur_currency,
                    line.employee_id.company_id,
                    line.date,
                )
                line.amount_eur = line.amount * currency_rate

    @api.depends("amount", "is_capitalized", "unit_amount")
    def _compute_capital_values(self):
        for line in self:
            capitalized = line.is_capitalized
            capital_labour_cost = line.amount if capitalized else 0.0
            percent_capital_labour_cost = (
                capital_labour_cost / line.amount if line.amount else 0.0
            )

            line.capital_labour_cost = capital_labour_cost
            line.capital_unit_amount = line.unit_amount if capitalized else 0.0
            line.percent_capital_labour_cost = percent_capital_labour_cost

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        """
        Failed with aggregator='avg': 100% + 0%(line without amount) = 50%.
        Redefine to ignore lines with a value of 0% when grouping.
        We divide capital_labour_cost by amount to get the correct value.
        """
        res = super().read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )
        for line in res:
            if line.get("amount"):
                line.update(
                    {
                        "percent_capital_labour_cost": abs(
                            (line.get("capital_labour_cost") or 0) / line.get("amount")
                        ),
                    }
                )
        return res
