# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
    )
