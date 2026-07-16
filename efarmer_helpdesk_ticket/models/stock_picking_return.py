from odoo import api, models

class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.depends('sale_order_id')
    def _compute_picking_id(self):
        super()._compute_picking_id()
        for r in self:
            if r.ticket_id.delivery_transfer_id and r.picking_id != r.ticket_id.delivery_transfer_id:
                r.picking_id = r.ticket_id.delivery_transfer_id
                r.sale_order_id = r.ticket_id.sale_order_id
