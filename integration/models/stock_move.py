# See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.tools import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    integration_external_id = fields.Char(
        related='sale_line_id.integration_external_id',
    )

    @property
    def has_kits(self):
        return any(getattr(x, 'bom_line_id', False) for x in self)

    def _get_new_picking_values(self):
        vals = super()._get_new_picking_values()
        integration = self.sale_line_id.order_id.integration_id

        if integration:
            src_field_name = integration.so_delivery_note_field.name
            tgt_field_name = integration.picking_delivery_note_field.name

            src_value = getattr(self.sale_line_id.order_id, src_field_name)
            if src_value:
                vals[tgt_field_name] = src_value
        return vals

    def _move_qty_lack(self):
        return self.compare_qty_to_realqty == -1

    def _has_enough_qty(self):
        return self.compare_qty_to_realqty <= 0

    @property
    def compare_qty_to_realqty(self):
        return float_compare(
            self.quantity_done,
            self.product_qty,
            precision_rounding=self.product_id.uom_id.rounding,
        )
