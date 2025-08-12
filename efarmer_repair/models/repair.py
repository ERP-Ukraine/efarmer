# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class RepairOrder(models.Model):
    _inherit = 'repair.line'

    @api.onchange('type')
    def onchange_operation_type(self):
        res = super().onchange_operation_type()
        if not self.repair_id:
            return res
        repair_dest_loc = self.env['stock.location'].search(
            [('is_repair_location_dest_id', '=', True), ('company_id', '=', self.repair_id.company_id.id)],
            limit=1
        )
        if repair_dest_loc:
            self.location_dest_id = repair_dest_loc.id
        
        return res
