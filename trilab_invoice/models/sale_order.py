from odoo import fields, models, api, _
from odoo.exceptions import UserError


DOWN_PAYMENT_SECTION_NAME = '*down-payment-section*'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    advance_invoices = fields.Many2many('account.move', compute='compute_advance_invoices', store=False)
    x_is_poland = fields.Boolean(compute='_x_compute_is_poland', string='Technical Field: Is Poland')

    @api.depends('company_id')
    def _x_compute_is_poland(self):
        for rec in self:
            rec.x_is_poland = rec.company_id.country_id.id == rec.env.ref('base.pl').id

    def compute_advance_invoices(self):
        for sale in self:
            sale.advance_invoices = (
                sale.order_line.filtered(lambda line: line.is_downpayment)
                .mapped('invoice_lines')
                .filtered(lambda line: line.currency_id.compare_amounts(line.credit, 0.0) == 1)
                .mapped('move_id')
            )

    def get_taxes_groups(self):
        taxes_groups = dict()
        for line in self.order_line.filtered(lambda lne: not lne.is_downpayment and not lne.display_type):
            taxes_groups.setdefault(
                line.tax_id.tax_group_id.name,
                {'base': 0.0, 'tax': 0.0, 'total': 0.0, 'tax_percent': (line.tax_id.amount / 100.0)},
            )

            group = taxes_groups[line.tax_id.tax_group_id.name]
            group['base'] += line.price_subtotal
            # group['base'] += line.price_subtotal
            # group['tax'] += line.price_tax
            # group['total'] += line.price_subtotal + line.price_tax

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
        for group in self.get_taxes_groups().values():
            for key, value in group.items():
                summary[key] += value

        return summary

    def check_advance_invoice_values(self):
        taxes = self.order_line.mapped('tax_id')
        for tax in taxes:
            lines = self.order_line.filtered(lambda line: line.tax_id.id == tax.id)
            order_value = sum(line.price_total for line in lines.filtered(lambda _l: not _l.is_downpayment))
            invoice_lines = (
                lines.filtered(lambda _l: _l.is_downpayment).mapped('invoice_lines').filtered(lambda _l: _l.credit > 0)
            )
            advance_value = sum(line.price_total for line in invoice_lines)

            if advance_value - order_value > 0.05:
                raise UserError(_('Value in advance invoices is greater than order value'))

    def _get_invoiceable_lines(self, final=False):
        if any(self.mapped('x_is_poland')) and 'selected_invoice_lines' in self.env.context:
            return self.order_line.filtered(lambda _l: _l.id in self.env.context['selected_invoice_lines'])

        return super()._get_invoiceable_lines(final)

    def _create_invoices(self, grouped=False, final=False, date=None):
        invoice_ids = super()._create_invoices(grouped, final, date)

        if self.env.company.country_id.id == self.env.ref('base.pl').id:
            # remove downpayment section name
            invoice_ids.line_ids.filtered(lambda rec: rec.name == DOWN_PAYMENT_SECTION_NAME).unlink()

            currency_rate = self.env['res.currency.rate'].browse(self.env.context.get('x_convert_rate', 0))

            if currency_rate:
                invoice_ids.write(
                    {
                        'narration': _(
                            'Rate %s with effective date: %s', currency_rate.inverse_company_rate, currency_rate.name
                        )
                    }
                )

        return invoice_ids

    @api.depends_context('x_convert_rate', 'x_partner_bank_id')
    def _prepare_invoice(self):
        # noinspection PyProtectedMember
        invoice_vals = super()._prepare_invoice()

        if not invoice_vals.get('x_invoice_sale_date'):
            invoice_vals['x_invoice_sale_date'] = fields.Date.context_today(self)

        if self.env.context.get('x_convert_rate'):
            currency_rate = self.env['res.currency.rate'].browse(self.env.context.get('x_convert_rate', 0))
            if currency_rate:
                invoice_vals['currency_id'] = self.env.ref('base.PLN').id
                invoice_vals['x_currency_rate'] = currency_rate.inverse_company_rate
                invoice_vals['narration'] = _(
                    'Rate %s with effective date: %s', currency_rate.inverse_company_rate, currency_rate.name
                )

        elif invoice_vals.get('currency_id') != self.company_id.currency_id.id:
            invoice_vals['x_currency_rate'] = self.env['res.currency']._get_conversion_rate(
                self.currency_id,
                self.company_id.currency_id,
                self.company_id or self.env.company,
                invoice_vals.get('x_invoice_sale_date')
                or invoice_vals.get('invoice_date')
                or invoice_vals.get('date')
                or fields.Date.context_today(self),
            )

        if 'x_partner_bank_id' in self.env.context:
            invoice_vals['partner_bank_id'] = self.env.context['x_partner_bank_id']

        return invoice_vals

    @api.model
    def _prepare_down_payment_section_line(self, **optional_values):
        if self.env.company.country_id.id == self.env.ref('base.pl').id:
            optional_values['name'] = DOWN_PAYMENT_SECTION_NAME
        return super()._prepare_down_payment_section_line(**optional_values)
