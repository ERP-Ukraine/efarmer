import json

from odoo import _, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class AccountMove(models.Model):
    _inherit = 'account.move'

    def x_get_taxes_groups(self):
        return self.line_ids.tax_group_id.mapped('name')

    @staticmethod
    def _x_prepare_tax_columns(invoice, tax_groups):
        tax_totals = json.loads(invoice.tax_totals_json)
        tax_groups = {group: 0 for group in tax_groups}
        sign = -1 if invoice.is_purchase_document() else 1
        sign *= invoice.x_invoice_sign
        for subtotal in tax_totals['subtotals']:
            for group in tax_totals['groups_by_subtotal'][subtotal['name']]:
                tax_groups[group['tax_group_name']] = abs(group['x_tax_group_amount_in_pln']) * sign
        return list(tax_groups.values())

    def _x_get_invoice_report_headers(self):
        headers = [
            _('Number'),
            _('Partner Name'),
            _('Invoice Date'),
            _('Sale Date'),
            _('Vat Date'),
            _('Address'),
            _('City'),
            _('Code'),
            _('NIP'),
            _('Fiscal Position'),
            _('Origin'),
            _('Salesperson'),
            _('Company'),
            _('Date Due'),
            _('State'),
            _('Correction Invoice Number'),
            _('Partner ID'),
            _('Currency'),
            _('Total Net in PLN'),
        ]
        empty_tax = _("Empty Tax")
        headers.extend([f'{tax or empty_tax} (PLN)' for tax in self.x_get_taxes_groups()])  # Taxes headers
        headers.append(_('Total Gross in PLN'))
        headers.append(_('Total Gross in Currency'))
        return headers

    def x_action_invoice_report_xlsx(self):
        table_rows = [[header for header in self._x_get_invoice_report_headers()]]

        # noinspection PyUnresolvedReferences
        translated_states = dict(self._fields['state']._description_selection(self.env))

        for invoice in self:
            sign = -1 if invoice.is_purchase_document() else 1
            sign *= invoice.x_invoice_sign
            row_values = [
                invoice.name,
                invoice.partner_id.name,
                invoice.invoice_date,
                invoice.x_invoice_sale_date,
                invoice.pl_vat_date,
                f"{invoice.partner_id.street or ''} {invoice.partner_id.street2 or ''}".strip(),
                invoice.partner_id.city,
                invoice.partner_id.zip,
                invoice.partner_id.vat,
                invoice.fiscal_position_id.name,
                invoice.invoice_origin,
                invoice.sudo().invoice_user_id.name,
                invoice.company_id.name,
                invoice.invoice_date_due or invoice.invoice_date,
                translated_states[invoice.state],
                invoice.refund_invoice_id.name or '',
                invoice.partner_id.id,
                invoice.currency_id.name,
                abs(invoice.amount_untaxed_signed) * sign,
            ]

            row_values.extend(self._x_prepare_tax_columns(invoice, self.x_get_taxes_groups()))
            row_values.append(abs(invoice.amount_total_signed) * sign)
            row_values.append(abs(invoice.amount_total) * sign)

            table_rows.append(row_values)

        if len(self) == 1:
            file_name = f'{self.name}.xlsx'
        else:
            file_name = _('invoices-report-%s', fields.Date.context_today(self).strftime(DEFAULT_SERVER_DATE_FORMAT))

        worksheet_name = _('Invoice Report')

        attachment_id = self.env['trilab.xlsx_helper'].create_xlsx_report(
            {worksheet_name: table_rows}, file_name, self[:1].id, self._name
        )

        return {'type': 'ir.actions.act_url', 'url': f'/web/content/{attachment_id.id}?download=true', 'target': 'self'}
