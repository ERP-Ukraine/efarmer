from odoo import api, models


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.depends('sale_order_id')
    def _compute_picking_id(self):
        super()._compute_picking_id()
        for r in self:
            if r.ticket_id.delivery_transfer_id and r.picking_id != r.ticket_id.delivery_transfer_id:
                r.picking_id = r.ticket_id.delivery_transfer_id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ticket = self.env['helpdesk.ticket'].browse(self.env.context.get('active_id'))
        if 'sale_order_id' in fields_list and ticket.sale_order_id:
            res['sale_order_id'] = ticket.sale_order_id.id
        return res
