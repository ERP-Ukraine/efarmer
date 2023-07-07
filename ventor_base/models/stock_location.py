# Copyright 2021 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


# Odoo:
from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    # store attribute for Group By 'Warehouse', locations tree view
    warehouse_id = fields.Many2one(store=True)
    is_pallet = fields.Boolean(string="Is Pallet")
