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

    work_type_id = fields.Many2one(
        comodel_name='youtrack.work.type',
        string='Work Type',
    )

    account_asset_counterpart_id = fields.Many2one(
        related="employee_id.account_asset_counterpart_id",
        string='Account Asset Counterpart',
        store=True,
    )

    def unlink(self):
        for line in self:
            if line.is_capitalized:
                raise UserError(_('You cannot delete a Capitalized analytic line.'))
        return super(AccountAnalyticLine, self).unlink()

    def write(self, vals):
        for line in self:
            if line.is_capitalized:
                raise UserError(_('You cannot edit a Capitalized analytic line.'))
        return super(AccountAnalyticLine, self).write(vals)
