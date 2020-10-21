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
                products = self.env['stock.quant'].search([('location_id', 'child_of', location.ids)]).mapped('product_id')
                action['domain'] = expression.AND([action['domain'], [('id', 'in', products.ids)]])

        return action
