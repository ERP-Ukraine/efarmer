from odoo import models
from odoo.osv import expression


class StockQuantityHistory(models.TransientModel):
    _inherit = 'stock.quantity.history'

    def open_at_date(self):
        action = super().open_at_date()

        inventorization_location_id = self.env.context.get('inventorization_location_id')
        if inventorization_location_id:
            location = self.env['stock.location'].browse(int(inventorization_location_id)).exists()
            if location:
                action['context']['location'] = location.id  # to compute product qty correctly
                action['context']['search_default_nonzero_qty_available'] = True

        return action
