from odoo import models
from odoo.tools import float_compare

class PO(models.Model):
    _inherit = 'purchase.order'

    def is_all_delivered(self):
        self.ensure_one()

        if self.state == 'cancel':
            return False

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for pol in self.order_line:
            if float_compare(pol.product_qty, pol.qty_received, precision_digits=precision):
                return False

        return True
