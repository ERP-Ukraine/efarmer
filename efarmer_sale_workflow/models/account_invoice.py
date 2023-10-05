# -*- coding: utf-8 -*-
# pylint: disable=protected-access

from odoo import fields, api, models
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = "account.move"

    current_rate_pln = fields.Float(string='Current Rate PLN', compute='_get_current_rate_pln', digits=(16, 4))

    def _get_current_rate_pln(self):
        currency_pln = self.env['res.currency'].search([('name', '=', 'PLN')])
        for move in self:
            account_payment_ids = self.env['account.payment'].search([('reconciled_invoice_ids', 'in', move.id)])
            invoice_date_rate_id = currency_pln.rate_ids.filtered(lambda x: x.name == move.invoice_date)
            default_rate = currency_pln.rate_ids.sorted(key='name', reverse=True)[0].company_rate
            account_payment_rate = 0
            invoice_date_rate = 0

            if account_payment_ids:
                payment_id = account_payment_ids.sorted(key='date', reverse=True)[0]
                payment_rate_id = currency_pln.rate_ids.filtered(lambda x: x.name == payment_id.date)
                account_payment_rate = payment_rate_id.company_rate
            if not account_payment_rate and move.invoice_date and invoice_date_rate_id:
                invoice_date_rate = invoice_date_rate_id.company_rate

            move.current_rate_pln = account_payment_rate or invoice_date_rate or default_rate

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
