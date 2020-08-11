from odoo import models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _prepare_invoice_values(self, order, name, amount, so_line):
        values = super()._prepare_invoice_values(order, name, amount, so_line)
        assert isinstance(values, dict)
        values.update({
            'utm_term_id': order.utm_term_id.id,
            'utm_content_id': order.utm_content_id.id,
        })
        return values
