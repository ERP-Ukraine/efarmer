# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class Task(models.Model):
    _inherit = 'project.task'

    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string='Product',
    )
