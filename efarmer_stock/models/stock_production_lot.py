# -*- coding: utf-8 -*-
# Copyright 2024 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    is_assigned = fields.Boolean(string='Assigned', help='Technical field to mark assigned serial numbers')

