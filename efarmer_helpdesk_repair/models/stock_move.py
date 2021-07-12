from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    helpdesk_repair_lot_id = fields.Many2one('stock.production.lot', 'Lot (repair)', readonly=True)

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        res = super()._prepare_move_line_vals(quantity, reserved_quant)

        if self.helpdesk_repair_lot_id:
            res['lot_id'] = self.helpdesk_repair_lot_id.id

        return res
