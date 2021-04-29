from odoo import api, fields, models
from odoo.tools import float_compare

class PO(models.Model):
    _inherit = 'purchase.order'

    all_received = fields.Boolean('All Received', compute='_compute_all_received', store=True)

    @api.depends('order_line', 'order_line.product_qty', 'order_line.qty_received')
    def _compute_all_received(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        for po in self:

            for pol in po.order_line:
                if float_compare(pol.product_qty, pol.qty_received, precision_digits=precision):
                    po.all_received = False
                    break
            else:
                po.all_received = True
