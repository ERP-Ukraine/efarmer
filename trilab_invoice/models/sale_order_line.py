from odoo import models, api


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
            invoice_value = sum(
                lne.qty_to_invoice * (lne[sum_field] / lne.product_uom_qty) for lne in invoice_lines
            )
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

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        for line in self.filtered(lambda x: x.is_downpayment and x.order_id.x_is_poland):
            # For down payment sale.order.line count only qty_invoiced from down payment invoices
            qty_invoiced = 0.0
            for invoice_line in line.invoice_lines.filtered(lambda x: x.move_id.is_downpayment):
                if invoice_line.move_id.state != 'cancel':
                    if invoice_line.move_id.move_type == 'out_invoice':
                        qty_invoiced += invoice_line.product_uom_id._compute_quantity(
                            invoice_line.quantity, line.product_uom
                        )
                    elif invoice_line.move_id.move_type == 'out_refund':
                        qty_invoiced -= invoice_line.product_uom_id._compute_quantity(
                            invoice_line.quantity, line.product_uom
                        )
            line.qty_invoiced = qty_invoiced

    def _compute_untaxed_amount_to_invoice(self):
        super()._compute_untaxed_amount_to_invoice()

        # ref #5016, handle edge case, when issuing down payment for sale order in draft state
        # temporarily change line state to done, recalc untaxed amount and then bring original status back
        for line in self.filtered(lambda rec: rec.is_downpayment and rec.state not in ('sale', 'done')):
            _tmp_state = line.state
            line.write({'state': 'done'})
            super(SaleOrderLine, line)._compute_untaxed_amount_to_invoice()
            line.write({'state': _tmp_state})
