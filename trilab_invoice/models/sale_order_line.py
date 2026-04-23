from odoo import models
from odoo.tools import float_compare, float_is_zero


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def x_get_final_price_unit(self):
        """Compute final price_unit for final invoices."""
        sum_price_unit = 0.0
        currency_id = self._context.get('x_convert_rate_id') and self.company_id.currency_id or self.currency_id

        for line_id in self.invoice_lines.filtered(lambda l_id: l_id.move_id.state == 'posted'):
            rounding = line_id.product_uom_id.rounding

            if float_is_zero(line_id.quantity, precision_rounding=rounding):
                continue

            if line_id.currency_id != currency_id:
                price_unit = line_id.currency_id._convert(
                    line_id.price_unit,
                    currency_id,
                    line_id.company_id,
                    line_id.move_id._get_invoice_currency_rate_date(),
                )
            else:
                price_unit = line_id.price_unit

            # For invoices use price_unit as is, for refunds negate price_unit on positive quantity lines.
            sum_price_unit += price_unit * (
                1
                if line_id.move_type == 'out_invoice'
                else float_compare(0.0, line_id.quantity, precision_rounding=rounding)
            )

        return sum_price_unit

    def _prepare_invoice_line(self, **optional_values):
        is_advance = self._context.get('x_advance', False)

        if is_advance:
            optional_values['name'] = self.product_id.display_name

        inv_line = super()._prepare_invoice_line(**optional_values)
        is_final_invoice_line = (
            is_advance
            and self.is_downpayment
            and self.invoice_lines.filtered(lambda l_id: l_id.move_id.state == 'posted')
        )
        final_price_unit = is_final_invoice_line and self.x_get_final_price_unit()

        if self._context.get('x_convert_rate_id') and (
            currency_rate := self.env['res.currency.rate'].browse(self.env.context.get('x_convert_rate_id'))
        ):
            # For final invoice lines with revaluation.
            if is_final_invoice_line:
                inv_line['price_unit'] = final_price_unit

            # For normal and advance invoice lines with revaluation.
            else:
                inv_line['price_unit'] *= currency_rate.inverse_company_rate

        # For final invoice lines.
        elif is_final_invoice_line:
            inv_line['price_unit'] = final_price_unit

        return inv_line

    def _compute_untaxed_amount_to_invoice(self):
        super()._compute_untaxed_amount_to_invoice()

        # ref #5016, handle edge case, when issuing down payment for sale order in draft state
        # temporarily change line state to sale, recalc untaxed amount and then bring original status back
        for line_id in self.filtered(lambda l_id: l_id.is_downpayment and l_id.state != 'sale'):
            _tmp_state = line_id.state
            line_id.write({'state': 'sale'})
            super(SaleOrderLine, line_id)._compute_untaxed_amount_to_invoice()
            line_id.write({'state': _tmp_state})
