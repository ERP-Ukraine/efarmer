# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    repair_location_dest_id = fields.Many2one("stock.location")
