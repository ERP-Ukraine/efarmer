from odoo import fields, models


class StockWarehouseLotPrefix(models.Model):
    _name = 'stock.warehouse.lot.prefix'
    _description = 'Mapping lots to warehouses'

    warehouse_id = fields.Many2one('stock.warehouse', required=True)
    lot_prefix = fields.Char(required=True)

    def name_get(self):
        return [(x.id, x.warehouse_id.display_name + ' / ' + x.lot_prefix) for x in self]
