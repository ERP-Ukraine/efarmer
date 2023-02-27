# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


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
