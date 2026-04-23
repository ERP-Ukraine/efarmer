from odoo import _, _lt, api, models
from odoo.addons.trilab_jpk_base.models.export_helper import CellDefinition


class InvoiceReport(models.AbstractModel):
    _name = 'report.trilab_jpk_vat.invoice_report'
    _inherit = ['jpk.trilab.export_helper']
    _description = 'Invoice Report'

    # noinspection PyArgumentList
    columns = [
        CellDefinition('name', _lt('Number')),
        CellDefinition('partner_name', _lt('Partner Name')),
        CellDefinition('invoice_date', _lt('Invoice Date'), 'date'),
        CellDefinition('x_invoice_sale_date', _lt('Sale Date'), 'date'),
        CellDefinition('pl_vat_date', _lt('Vat Date'), 'date'),
        CellDefinition('address', _lt('Address')),
        CellDefinition('city', _lt('City')),
        CellDefinition('zip_code', _lt('Code')),
        CellDefinition('vat', _lt('NIP')),
        CellDefinition('fp', _lt('Fiscal Position')),
        CellDefinition('origin', _lt('Origin')),
        CellDefinition('salesperson', _lt('Salesperson')),
        CellDefinition('company', _lt('Company')),
        CellDefinition('due_date', _lt('Date Due'), 'date'),
        CellDefinition('state', _lt('State')),
        CellDefinition('refunded', _lt('Correction Invoice Number')),
        CellDefinition('partner_id', _lt('Partner ID')),
        CellDefinition('currency', _lt('Currency')),
        CellDefinition('total', _lt('Total Net in base currency'), 'float', 'monetary'),
    ]

    tax_columns = []

    extra_columns = [
        CellDefinition('refunded', _lt('Total Gross in base currency'), 'float', 'monetary'),
        CellDefinition('partner_id', _lt('Total Gross in Currency'), 'float', 'monetary'),
    ]

    @staticmethod
    def _x_prepare_tax_columns(invoice, tax_groups):
        tax_groups = {group: 0 for group in tax_groups}
        sign = -1 if invoice.is_purchase_document() else 1

        for subtotal in invoice.tax_totals['subtotals']:
            for group in invoice.tax_totals['groups_by_subtotal'][subtotal['name']]:
                tax_groups[group['tax_group_name']] = group['x_tax_group_amount_local'] * sign

        return list(tax_groups.values())

    @api.model
    def _get_report_data(self, docids, options):
        # headers
        table_rows = [
            [str(cell.name) for cell in self.columns] + ['tmp-taxes'] + [str(cell.name) for cell in self.extra_columns]
        ]

        translated_states = dict(self.env['account.move']._fields['state']._description_selection(self.env))
        tax_groups = set()

        for invoice_id in self.env['account.move'].browse(docids):
            sign = -1 if invoice_id.is_purchase_document() else 1

            invoice_tax_groups = {}

            for subtotal in invoice_id.tax_totals['subtotals']:
                for group in subtotal['tax_groups']:
                    # todo VERIFY R18!
                    # invoice_tax_groups[group['group_name']] = group['x_tax_group_amount_local'] * sign
                    invoice_tax_groups[group['group_name']] = group['tax_amount'] * sign
                    tax_groups.add(group['group_name'])

            table_rows.append(
                [
                    invoice_id.name,
                    invoice_id.partner_id.name,
                    invoice_id.invoice_date,
                    invoice_id.x_invoice_sale_date,
                    invoice_id.pl_vat_date,
                    f'{invoice_id.partner_id.street or ""} {invoice_id.partner_id.street2 or ""}'.strip(),
                    invoice_id.partner_id.city,
                    invoice_id.partner_id.zip,
                    invoice_id.partner_id.vat,
                    invoice_id.fiscal_position_id.name,
                    invoice_id.invoice_origin,
                    invoice_id.sudo().invoice_user_id.name,
                    invoice_id.company_id.name,
                    invoice_id.invoice_date_due or invoice_id.invoice_date,
                    translated_states[invoice_id.state],
                    invoice_id.reversed_entry_id.name or '',
                    invoice_id.partner_id.id,
                    invoice_id.currency_id.name,
                    abs(invoice_id.amount_untaxed_signed) * sign,
                    invoice_tax_groups,
                    abs(invoice_id.amount_total_signed) * sign,
                    abs(invoice_id.amount_total) * sign,
                ]
            )

        # expand taxes
        tax_groups = sorted(tax_groups)

        for y, row in enumerate(table_rows):
            new_row = row[:19]
            reminder = row[20:]

            if y == 0:
                new_row += [name for name in tax_groups]

            else:
                new_row += [row[19].get(name) for name in tax_groups]

            new_row += reminder

            table_rows[y] = new_row

        return table_rows

    @api.model
    def _get_report_name(self):
        return _('Invoice Report')

    def generate_xlsx_report(self, workbook, doc_ids, options):
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        # Iterate over worksheet_data by columns and set max column width
        max_widths = []
        columns = []

        for y, row in enumerate(self._get_report_data(doc_ids, options)):
            if not columns:
                columns = self.columns + [
                    CellDefinition(name, name, 'float', 'monetary') for name in row[len(self.columns) :]
                ]

            if not max_widths:
                max_widths = [0] * len(row)

            for x, value in enumerate(row):
                self._write_cell(sheet, y, x, value, definition=columns[x] if x < len(columns) else None)
                max_widths[x] = max(max_widths[x], len(str(value)))

        for x, width in enumerate(max_widths):
            sheet.set_column(x, x, width + 10)
