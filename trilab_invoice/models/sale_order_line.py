from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _x_prepare_invoice_line(self, line_list=False, **optional_values):
        self.ensure_one()
        quantity = self.qty_to_invoice
        if self.is_downpayment and line_list and quantity < 0:
            sum_field = 'price_total' if self.tax_id.price_include else 'price_subtotal'
            invoice_lines = line_list.filtered(lambda lne: not lne.is_downpayment and lne.tax_id.ids == self.tax_id.ids)
            so_lines = self.order_id.order_line.filtered(
                lambda line: not line.is_downpayment and line.tax_id.ids == self.tax_id.ids
            )
            invoice_value = sum(lne.qty_to_invoice * (lne[sum_field] / lne.product_uom_qty) for lne in invoice_lines)
            so_value = sum(line[sum_field] for line in so_lines)
            quantity = -1 * (invoice_value / so_value)
        res = self._prepare_invoice_line(sequence=optional_values['sequence'])
        res['quantity'] = quantity
        return res

    def _prepare_invoice_line(self, **optional_values):
        inv_line = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)

        if self.env.context.get('x_convert_rate'):
            currency_rate = self.env['res.currency.rate'].browse(self.env.context.get('x_convert_rate', 0))
            if currency_rate:
                inv_line['price_unit'] *= currency_rate.inverse_company_rate

        return inv_line

    def _compute_untaxed_amount_to_invoice(self):
        super()._compute_untaxed_amount_to_invoice()

        # ref #5016, handle edge case, when issuing down payment for sale order in draft state
        # temporarily change line state to done, recalc untaxed amount and then bring original status back
        for line in self.filtered(lambda rec: rec.is_downpayment and rec.state not in ('sale', 'done')):
            _tmp_state = line.state
            line.write({'state': 'done'})
            super(SaleOrderLine, line)._compute_untaxed_amount_to_invoice()
            line.write({'state': _tmp_state})
