# -*- coding: utf-8 -*-
# pylint: disable=protected-access

from odoo import fields, api, models, _
from odoo.tools import float_compare

from datetime import timedelta


class AccountMove(models.Model):
    _inherit = "account.move"

    # Technical field
    # Task EF-252
    _current_rate_pln = fields.Boolean(string='Current Rate PLN', compute='_get_current_rate_pln',)
    is_manually_current_rate = fields.Boolean('Manually Current Rate')
    current_rate_pln = fields.Float(string='Current Rate PLN', digits=(16, 4))
    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='VAT ID',
    )

    def get_report_vat_text_line(self):
        self.ensure_one()
        if not self.company_id.additional_vat_note:
            return ""

        eu_country_ids = self.env.ref('base.europe').country_ids
        nl_country_id = self.env.ref("base.nl")
        pl_country_id = self.env.ref("base.pl")
        product_types = set(self.invoice_line_ids.mapped('product_id.type'))
        product_types.discard('consu')

        if (
            {'service'} == product_types
            and self.commercial_partner_id.company_type == 'company'
            and self.commercial_partner_id.country_id != nl_country_id
            and self.commercial_partner_id.country_id in eu_country_ids
        ):
            return _("Reverse charge applies (Art. 196 VAT Directive 2006/112/EC).")
        elif (
            ({'product'} == product_types or {'service', 'product'} == product_types)
            and self.commercial_partner_id.company_type == 'company'
            and self.commercial_partner_id.country_id != pl_country_id
            and self.commercial_partner_id.country_id in eu_country_ids
        ):
            return _("VAT exempt according to art.138 VAT Directive 2006/112/EC")
        elif (
            ({'product'} == product_types or {'service', 'product'} == product_types)
            and self.commercial_partner_id.company_type in ('company', 'person')
            and self.commercial_partner_id.country_id not in eu_country_ids
        ):
            return _("VAT exempt according to art.146 VAT Directive 2006/112/EC")

        return ""

    def _get_current_rate_pln(self):
        # this function is needed to take the exchange rate for the previous day
        # If it is Monday, Saturday, Sunday then take the date as Friday
        # If other days then take the previous date
        def _get_currency_rate_on_yesterday(currency_date):
            if currency_date.weekday() == 0:  # 0 - monday,
                currency_date -= timedelta(days=3)
            elif currency_date.weekday() == 6:  # 6 - sunday
                currency_date -= timedelta(days=2)
            else:  # date - 1 day
                currency_date -= timedelta(days=1)

            return currency_date

        currency_pln = self.env['res.currency'].search([('name', '=', 'PLN')])
        for move in self:
            move._current_rate_pln = True
            if move.is_manually_current_rate:
                return

            account_payment_ids = self.env['account.payment'].search([('ref', '=', move.payment_reference)])
            if move.invoice_date:
                invoice_date_rate_id = currency_pln.rate_ids.filtered(
                    lambda x: x.name == _get_currency_rate_on_yesterday(move.invoice_date) and
                              x.company_id == move.company_id
                )
            default_rate = currency_pln.rate_ids.filtered(
                lambda x: x.company_id == move.company_id
            ).sorted(key='name', reverse=True)[0].company_rate
            account_payment_rate = 0
            invoice_date_rate = 0

            if account_payment_ids:
                payment_id = account_payment_ids.sorted(key='date', reverse=True)[0]
                payment_rate_id = currency_pln.rate_ids.filtered(
                    lambda x: x.name == _get_currency_rate_on_yesterday(payment_id.date) and
                              x.company_id == move.company_id
                )
                account_payment_rate = payment_rate_id.company_rate
            if not account_payment_rate and move.invoice_date and invoice_date_rate_id:
                invoice_date_rate = invoice_date_rate_id.company_rate

            move.current_rate_pln = account_payment_rate or invoice_date_rate or default_rate
            if move.invoice_line_ids and move.invoice_line_ids.sale_line_ids:
                move.product_vat_id = move.invoice_line_ids.sale_line_ids[0].order_id.product_vat_id

    def _recompute_amount(self):
        """ Before turning data into JSON we need to filter account move lines
            so there no deposit lines left
            same logic as in move._compute_amount()
        """
        currencies = self._get_lines_onchange_currency().currency_id
        total = 0.0
        total_currency = 0.0
        total_untaxed = 0.0
        total_untaxed_currency = 0.0
        for line in self.line_ids.filtered(lambda line: not line.has_deposit_deducted()):
            if self._payment_state_matters():
                # === Invoices ===
                if not line.exclude_from_invoice_tab:
                    total_untaxed += line.balance
                    total_untaxed_currency += line.amount_currency
                    total += line.balance
                    total_currency += line.amount_currency
                elif line.tax_line_id:
                    total += line.balance
                    total_currency += line.amount_currency
            else:
                if line.debit:
                    total += line.balance
                    total_currency += line.amount_currency

        sign = 1 if self.move_type == 'entry' or self.is_outbound() else -1
        amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
        amount_total = sign * (total_currency if len(currencies) == 1 else total)
        return amount_total, amount_untaxed

    def _prepare_tax_lines_data_for_totals_from_invoice(self, tax_line_id_filter=None, tax_ids_filter=None):
        skip_deposit = self._context.get('without_deposit')
        if not skip_deposit:
            return super()._prepare_tax_lines_data_for_totals_from_invoice(tax_line_id_filter, tax_ids_filter)

        return super()._prepare_tax_lines_data_for_totals_from_invoice(lambda aml, tax: not aml.has_deposit_deducted(), lambda aml, tax: not aml.has_deposit_deducted())

    @api.model
    def _get_tax_totals(self, partner, tax_lines_data, amount_total, amount_untaxed, currency):
        skip_deposit = self._context.get('without_deposit')
        if not skip_deposit:
            return super()._get_tax_totals(partner, tax_lines_data, amount_total, amount_untaxed, currency)

        amount_total_skip_deposit, amount_untaxed_skip_deposit = self._recompute_amount()
        return super()._get_tax_totals(partner, tax_lines_data, amount_total_skip_deposit, amount_untaxed_skip_deposit, currency)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def has_deposit_deducted(self):
        """Checks if current line has deposit with negative subtotal."""
        self.ensure_one()
        deposit_product_id = self.env['ir.config_parameter'].sudo(
            ).get_param('sale.default_deposit_product_id')
        if not deposit_product_id:
            return False
        if self.product_id.id == int(deposit_product_id):
            precision = self.move_id.currency_id.rounding
            if float_compare(self.price_subtotal, 0.0, precision_rounding=precision) == -1:
                return True
        return False
