# Copyright 2025 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    analytic_tag_ids = fields.Many2many(
        comodel_name='account.analytic.tag',
        string='Analytic Tags',
        compute="_compute_analytic_tag_ids",
        inverse="_inverse_analytic_tag_ids",
        readonly=False,
        store=False,
        check_company=True,
    )

    @api.depends(
        "move_id",
        "move_id.line_ids",
        "move_id.line_ids.analytic_tag_ids",
    )
    def _compute_analytic_tag_ids(self):
        for line in self:
            line.analytic_tag_ids = line.mapped('move_id.line_ids.analytic_tag_ids')

    def _inverse_analytic_tag_ids(self):
        for line in self:
            line.move_id.line_ids.write({"analytic_tag_ids": [fields.Command.set(line.analytic_tag_ids.ids)]})
