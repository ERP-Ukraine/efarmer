from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # Make it uncopyable.
    picking_ids = fields.Many2many('stock.picking', copy=False)

    # A warehouse where products are repairing.
    factory_id = fields.Many2one('stock.warehouse', 'Factory')

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        product_domain = []
        lot_domain = []

        if self.sale_order_id:
            self.product_id = False
            self.lot_id = False
            self.factory_id = False

            product_domain.append(('id', 'in', self.sale_order_id.mapped('order_line.product_id').ids))
            lot_domain.append(('id', 'in', self.sale_order_id.mapped('order_line.move_ids.move_line_ids.lot_id').ids))

        return {
            'domain': {
                'product_id': product_domain,
                'lot_id': lot_domain,
            },
        }

    @api.onchange('product_id')
    def _onchange_product_id(self):
        lot_domain = []

        if self.product_id:

            if self.lot_id and self.lot_id.product_id != self.product_id:
                self.lot_id = False

            lot_domain.append(('product_id', '=', self.product_id.id))
            if self.sale_order_id:
                lot_domain.append(('id', 'in', self.sale_order_id.mapped('order_line.move_ids.move_line_ids.lot_id').ids))

        return {
            'domain': {'lot_id': lot_domain},
        }

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        factory_domain = []

        if self.lot_id:

            if not self.product_id or self.product_id != self.lot_id.product_id:
                self.product_id = self.lot_id.product_id

            warehouses = self.env['stock.warehouse.lot.prefix'].search([]).filtered(lambda x: self.lot_id.display_name.startswith(x.lot_prefix)).mapped('warehouse_id')
            if warehouses:

                if len(warehouses) == 1 and self.factory_id != warehouses:
                    self.factory_id = warehouses
                elif self.factory_id and self.factory_id not in warehouses:
                    self.factory_id = False

                factory_domain.append(('id', 'in', warehouses.ids))

        return {
            'domain': {'factory_id': factory_domain},
        }
