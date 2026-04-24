# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models


class StockMove(models.Model):
    _name = 'stock.move'
    _inherit = ['stock.move', 'printnode.mixin']

    def _action_assign(self, force_qty=False):
        # Overridden to catch transfer status changes and handle cases with
        # different Shipping Policy values selected for the transfer.
        # Check tickets VENSUP-15754 and VENSUP-15819 for more details
        picking_ids = self.mapped('picking_id')
        previous_states = {rec.id: rec.state for rec in picking_ids}

        super(StockMove, self)._action_assign(force_qty)

        for picking in picking_ids:
            # with_company() used to print on correct printer when calling from scheduled actions
            if picking.id and previous_states.get(picking.id) != picking.state:
                picking.with_company(picking.company_id).print_scenarios(
                    'print_document_on_picking_status_change')
