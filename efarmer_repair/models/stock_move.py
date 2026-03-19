# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends("repair_id.location_dest_id", "repair_line_type")
    def _compute_location_dest_id(self):
        res = super()._compute_location_dest_id()
        if not self.repair_id:
            return res
        repair_dest_loc = self.repair_id.picking_type_id.repair_location_dest_id
        if repair_dest_loc:
            self.location_dest_id = repair_dest_loc.id
        return res
