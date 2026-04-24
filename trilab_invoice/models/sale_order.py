from odoo import _, api, fields, models
from odoo.exceptions import UserError

DOWN_PAYMENT_SECTION_NAME = '*down-payment-section*'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_use_ti = fields.Boolean(related='company_id.x_use_ti', string='Technical Field: Use Trilab Invoice')
    x_company_partner_bank_on_proforma = fields.Boolean(related='company_id.x_company_partner_bank_on_proforma')
    x_company_partner_bank_id = fields.Many2one(
        'res.partner.bank',
        'Company Partner Bank',
        compute='_x_compute_company_partner_bank_id',
        domain="[('currency_id', '=', currency_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        store=True,
    )

    @api.depends('currency_id', 'company_id')
    def _x_compute_company_partner_bank_id(self):
        for order_id in self:
            order_id.x_company_partner_bank_id = fields.first(
                order_id.company_id.partner_id.bank_ids.filtered(
                    lambda bank_id: (
                        bank_id.currency_id == order_id.currency_id
                        and (not bank_id.company_id or bank_id.company_id == order_id.company_id)
                    )
                )
            )

    def x_get_advance_invoices(self):
        return (
            self.order_line.filtered('is_downpayment')
            .invoice_lines.filtered(lambda line: line.currency_id.compare_amounts(line.credit, 0.0) == 1)
            .move_id
        )

    def x_get_taxes_groups(self):
        taxes_groups = {}
        for line_id in self.order_line.filtered(lambda lne: not lne.is_downpayment and not lne.display_type):
            taxes_groups.setdefault(
                line_id.tax_id.tax_group_id.name,
                {'base': 0.0, 'tax': 0.0, 'total': 0.0, 'tax_percent': (line_id.tax_id.amount / 100.0)},
            )

            group = taxes_groups[line_id.tax_id.tax_group_id.name]
            group['base'] += line_id.price_subtotal

        # rounding
        for tax_name in taxes_groups:
            tax_group = taxes_groups[tax_name]
            tax_group['base'] = self.currency_id.round(tax_group['base'])
            tax_group['tax'] = self.currency_id.round(tax_group['base'] * tax_group['tax_percent'])
            tax_group['total'] = tax_group['base'] + tax_group['tax']
            del tax_group['tax_percent']

        return taxes_groups

    def x_get_taxes_summary(self):
        summary = {'base': 0.0, 'tax': 0.0, 'total': 0.0}
        for group in self.x_get_taxes_groups().values():
            for key, value in group.items():
                summary[key] += value

        return summary

    def check_advance_invoice_values(self):
        for tax_id in self.order_line.mapped('tax_id'):
            line_ids = self.order_line.filtered(lambda l_id: l_id.tax_id.id == tax_id.id)
            order_value = sum(line_ids.filtered(lambda l_id: not l_id.is_downpayment).mapped('price_total'))
            advance_value = sum(
                line_ids.filtered('is_downpayment')
                .invoice_lines.filtered(lambda l_id: l_id.currency_id.compare_amounts(l_id.credit, 0) == 1)
                .mapped('price_total')
            )

            if advance_value - order_value > 0.05:
                raise UserError(_('Value in advance invoices is greater than order value'))

    def _get_invoiceable_lines(self, final=False):
        # todo handle sections
        line_ids = super()._get_invoiceable_lines(final)

        if any(self.mapped('x_use_ti')) and (lines := self.env.context.get('selected_invoice_lines', [])):
            return line_ids.filtered(lambda l_id: l_id.id in lines)

        return line_ids

    def _create_invoices(self, grouped=False, final=False, date=None):
        invoice_ids = super(
            SaleOrder, self.with_context(x_disable_refund_switch=any(self.mapped('x_use_ti')))
        )._create_invoices(grouped, final, date)

        if ti_invoice_ids := invoice_ids.filtered('x_use_ti'):
            # remove downpayment section name
            ti_invoice_ids.line_ids.filtered(lambda l_id: l_id.name == DOWN_PAYMENT_SECTION_NAME).with_context(
                check_move_validity=False, skip_invoice_sync=True
            ).unlink()

            currency_rate = self.env['res.currency.rate'].browse(self.env.context.get('x_convert_rate_id'))

            if currency_rate:
                # noinspection PyUnusedLocal
                context = {'lang': self.partner_id.lang}
                ti_invoice_ids.write(
                    {
                        'narration': _(
                            'Rate %s with effective date: %s',
                            f'{currency_rate.inverse_company_rate:.4f}',
                            currency_rate.name,
                        )
                    }
                )

        return invoice_ids

    @api.depends_context('x_convert_rate_id', 'x_partner_bank_id')
    def _prepare_invoice(self):
        context = {'lang': self.partner_id.lang}
        self = self.with_context(**context)

        invoice_vals = super()._prepare_invoice()

        if not invoice_vals.get('x_invoice_sale_date'):
            invoice_vals['x_invoice_sale_date'] = fields.Date.context_today(self)

        if (rate := self.env.context.get('x_convert_rate_id')) and (
            currency_rate := self.env['res.currency.rate'].browse(rate)
        ):
            invoice_vals['currency_id'] = self.company_id.currency_id.id
            invoice_vals['invoice_currency_rate'] = currency_rate.company_rate
            invoice_vals['narration'] = _(
                'Rate %s with effective date: %s',
                f'{currency_rate.inverse_company_rate:.4f}',
                currency_rate.name,
            )

        elif invoice_vals.get('currency_id') != self.company_id.currency_id.id:
            invoice_vals['invoice_currency_rate'] = self.env['res.currency']._get_conversion_rate(
                self.company_id.currency_id,
                self.currency_id,
                self.company_id or self.env.company,
                invoice_vals.get('x_invoice_sale_date')
                or invoice_vals.get('invoice_date')
                or invoice_vals.get('date')
                or fields.Date.context_today(self),
            )

        if x_partner_bank_id := self.env.context.get('x_partner_bank_id'):
            invoice_vals['partner_bank_id'] = x_partner_bank_id

        return invoice_vals

    def _prepare_down_payment_section_line(self, **optional_values):
        if self.x_use_ti:
            optional_values['name'] = DOWN_PAYMENT_SECTION_NAME
        return super()._prepare_down_payment_section_line(**optional_values)
