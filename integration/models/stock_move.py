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

    def _assign_picking_post_process(self, *args, **kwargs):
        result = super()._assign_picking_post_process(*args, **kwargs)

        for picking in self.mapped('picking_id'):
            integration = picking.sale_id.integration_id

            if integration:
                source_note_name = integration.so_delivery_note_field.name
                target_note_name = integration.picking_delivery_note_field.name

                if source_note_name and target_note_name:
                    value = getattr(picking.sale_id, source_note_name)

                    if value:
                        picking.write({target_note_name: value})

        return result

    def _move_qty_lack(self):
        return self.compare_qty_to_realqty == -1

    def _has_enough_qty(self):
        return self.compare_qty_to_realqty <= 0

    @property
    def compare_qty_to_realqty(self):
        return float_compare(
            self.quantity,
            self.product_qty,
            precision_rounding=self.product_id.uom_id.rounding,
        )
