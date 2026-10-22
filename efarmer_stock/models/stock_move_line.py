# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    return_lot_ids = fields.Many2many('stock.lot', compute='_compute_return_lot_ids')

    @api.depends('move_id.origin_returned_move_id')
    def _compute_return_lot_ids(self):
        for line in self:
            line.return_lot_ids = line.move_id.origin_returned_move_id.move_line_ids.lot_id
