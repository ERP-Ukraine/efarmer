# See LICENSE file for full copyright and licensing details.

from functools import reduce

from odoo import models
from odoo.tools.misc import groupby


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _run_integration_picking_hooks(self):
        """
        Redefined method for Shopify in order to perform
        partial validation (integration_send_picking)
        """
        for order, picking_list in groupby(self, key=lambda x: x.sale_id):
            integration = order.integration_id
            if not integration:
                continue

            if not integration.is_shopify():
                pickings = reduce(lambda x, y: x + y, picking_list)
                super(StockPicking, pickings)._run_integration_picking_hooks()
                continue

            # A: send full delivery validation and continue
            if order.check_is_order_shipped():
                order._integration_shipped_order_hook()
                order.order_export_tracking()
                continue

            # B: send partial delivery validation or awaiting full Odoo validation (case A)
            if not order.is_procurement_grouped:
                continue

            for rec in [x for x in picking_list if x.no_kits]:
                rec.integration_send_picking()
