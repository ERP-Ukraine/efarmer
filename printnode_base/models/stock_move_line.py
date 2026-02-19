# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, models


REAL_TIME_SCENARIO_ACTIONS = [
    'print_single_lot_label_on_transfer',
    'print_multiple_lot_labels_on_transfer',
    'print_single_product_label_on_transfer',
    'print_multiple_product_labels_on_transfer',
]


class StockMoveLine(models.Model):
    _name = 'stock.move.line'
    _inherit = ['stock.move.line', 'printnode.mixin', 'printnode.scenario.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        mls = super().create(vals_list)

        mls_picked = mls.filtered(lambda ml: ml.picked)
        if mls_picked:
            self._call_scenarios(mls_picked)

        return mls

    def write(self, vals):
        changed_move_lines = self.env['stock.move.line']
        for move_line in self:
            quantity = vals.get('quantity')
            qty_done = vals.get('qty_done')
            picked = vals.get('picked')

            # If quantity is updated from Ventor PRO
            if quantity and quantity > 0 and picked:
                changed_move_lines |= move_line

            # Additional case: stock_barcode module is installed
            # qty_done field will be there only if this module is installed
            elif qty_done and qty_done > 0:
                changed_move_lines |= move_line

        res = super().write(vals)

        self._call_scenarios(changed_move_lines)

        return res

    def _call_scenarios(self, mls):
        # These scenarios shouldn't be run from crons
        if mls and not self.env.context.get('printnode_from_cron', False):
            for action in REAL_TIME_SCENARIO_ACTIONS:
                self.print_scenarios(
                    action=action,
                    ids_list=mls.mapped('picking_id.id'),
                    changed_move_lines=mls)
