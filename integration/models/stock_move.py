# Copyright 2021 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).


# Odoo:
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

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
