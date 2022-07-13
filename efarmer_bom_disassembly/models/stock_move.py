from odoo import models
from odoo.tools import float_compare, float_round


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_price_unit(self):
        self.ensure_one()
        if self.production_id.bom_id.disassembly:
            return self.product_id.standard_price
        else:
            return super()._get_price_unit()

    def product_price_update_before_done(self, forced_qty=None):
        processed_moves = self.product_price_update_before_done_disassembly(forced_qty)
        other_moves = self - processed_moves

        if other_moves:
            return super(StockMove, other_moves).product_price_update_before_done(forced_qty)
        else:
            return True

    def product_price_update_before_done_disassembly(self, forced_qty=None):
        """Total sum of materials should be equal to total sum of products in case of a disassembly."""
        def filter_out_moves(move):
            is_in = move._is_in()
            is_disassembly = move.production_id.bom_id.disassembly
            has_valid_state = move.state not in ('done', 'cancel')
            return is_in and is_disassembly and has_valid_state

        moves = self.filtered(filter_out_moves)

        sale_price_digits = self.env['decimal.precision'].precision_get('Product Price')

        for production in moves.mapped('production_id'):
            raw_layers = production.move_raw_ids.stock_valuation_layer_ids
            if not raw_layers:
                continue

            out_total_value = abs(sum(raw_layers.mapped('value')))

            in_total_qty = 0.0
            in_total_value = 0.0
            move_data = {}
            for move in production.move_finished_ids:
                qty_done = 0
                for move_line in move._get_in_move_lines():
                    qty_done += move_line.product_uom_id._compute_quantity(move_line.qty_done, move.product_id.uom_id)

                qty = forced_qty or qty_done
                price_unit = move.product_id.with_company(move.company_id).standard_price

                in_total_qty += qty
                in_total_value += price_unit * qty
                move_data[move.id] = {'qty': qty, 'price_unit': price_unit}

            if not float_compare(out_total_value, in_total_value, precision_digits=sale_price_digits):
                continue

            extra_price_unit = (out_total_value - in_total_value) / in_total_qty

            in_total_value_new = 0.0
            for i, move in enumerate(production.move_finished_ids, start=1):
                if i == len(production.move_finished_ids):
                    price = (out_total_value - in_total_value_new) / move_data[move.id]['qty']
                else:
                    price = move_data[move.id]['price_unit'] + extra_price_unit
                price = float_round(price, precision_digits=sale_price_digits)

                move.product_id.with_company(move.company_id).sudo().write({'standard_price': price})
                in_total_value_new += price * move_data[move.id]['qty']

        return moves
