# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    available_location_ids = fields.Many2many(
        comodel_name="stock.location",
        relation="res_users_available_stock_location_rel",
        column1="user_id",
        column2="location_id",
        string="Available Locations",
        domain="[('usage', 'in', ('internal', 'view'))]",
        help="Source and destination locations (including their sublocations) the user can use "
        "in internal transfers. Leave empty to allow all locations.",
    )
