# -*- coding: utf-8 -*-
# pylint: disable=protected-access

from odoo import api, fields, models
from odoo.tools import float_compare
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_deposit_line_taxes(self):
        self.ensure_one()
        tax_grouped = {}
        round_curr = self.currency_id.round
        for line in self.invoice_line_ids:
            if not line.has_deposit_deducted():
                continue
            price_unit = line.price_unit * (1 - (line.discount / 100.0))
            taxes = line.tax_ids.compute_all(price_unit, currency=self.currency_id,
                                             quantity=line.quantity, product=line.product_id,
                                             partner=self.partner_id)['taxes']
            for tax in taxes:
                # if tax['tax_exigibility'] != 'on_invoice':
                #     continue
                tax_id = self.env['account.tax'].browse(tax['id'])
                group_key = (tax_id.id, tax_id.tax_group_id.id)
                tax_grouped.setdefault(group_key, {'base': 0.0, 'amount': 0.0})
                tax_grouped[group_key]['amount'] += round_curr(tax['amount'])
                tax_grouped[group_key]['base'] += round_curr(tax['base'])
        return tax_grouped

    @api.depends('line_ids.price_subtotal', 'line_ids.tax_base_amount',
                 'line_ids.tax_line_id', 'partner_id', 'currency_id')
    def _compute_invoice_taxes_by_group(self):
        """Helper to get the taxes grouped according their account.tax.group.

        This method is only used when printing the invoice."""

        skip_deposit = self._context.get('without_deposit')
        for move in self:
            # added lines
            deposit_taxes = move._get_deposit_line_taxes() if skip_deposit else {}
            # end of added lines
            lang_env = move.with_context(lang=move.partner_id.lang).env
            tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id)
            res = {}
            # There are as many tax line as there are repartition lines
            done_taxes = set()
            for line in tax_lines:
                # added lines: skip cash basis tax lines
                # if line.tax_line_id.tax_exigibility != 'on_invoice':
                #     continue
                # end of added lines
                res.setdefault(line.tax_line_id.tax_group_id, {'base': 0.0, 'amount': 0.0})
                # added lines: compensate negative deposit taxes
                group_key = (line.tax_line_id.id, line.tax_line_id.tax_group_id.id)
                tax_group = line.tax_line_id.tax_group_id
                if skip_deposit and group_key in deposit_taxes:
                    res[tax_group]['amount'] -= deposit_taxes[group_key]['amount']
                    res[tax_group]['base'] -= deposit_taxes[group_key]['base']
                # end of added lines
                res[line.tax_line_id.tax_group_id]['amount'] += line.price_subtotal
                tax_key_add_base = tuple(move._get_tax_key_for_group_add_base(line))
                if tax_key_add_base not in done_taxes:
                    if line.currency_id != self.company_id.currency_id:
                        amount = self.company_id.currency_id._convert(
                            line.tax_base_amount, line.currency_id, self.company_id,
                            line.date or fields.Date.today())
                    else:
                        amount = line.tax_base_amount
                    res[line.tax_line_id.tax_group_id]['base'] += amount
                    # The base should be added ONCE
                    done_taxes.add(tax_key_add_base)
            res = sorted(res.items(), key=lambda l: l[0].sequence)
            move.amount_by_group = [(
                group.name, amounts['amount'],
                amounts['base'],
                formatLang(lang_env, amounts['amount'], currency_obj=move.currency_id),
                formatLang(lang_env, amounts['base'], currency_obj=move.currency_id),
                len(res),
                group.id
            ) for group, amounts in res]


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
