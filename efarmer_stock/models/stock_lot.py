# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    is_assigned = fields.Boolean(
        string="Assigned", help="Technical field to mark assigned serial numbers"
    )
