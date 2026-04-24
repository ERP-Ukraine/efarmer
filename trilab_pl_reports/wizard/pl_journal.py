from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.addons.trilab_jpk_base.models.export_helper import CellDefinition


class JournalReportWizard(models.TransientModel):
    _name = 'pl.journal.report.wizard'
    _description = 'PL Journal Report Wizard'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    date_from = fields.Date(
        string='Start Date', default=lambda self: fields.Date.today() + relativedelta(day=1, months=-1)
    )

    date_to = fields.Date(
        string='End Date', default=lambda self: fields.Date.today() + relativedelta(day=31, months=-1)
    )

    target_move = fields.Selection(
        [('posted', 'All Posted Entries'), ('all', 'All Entries')], string='Target Moves', default='posted'
    )

    journal_ids = fields.Many2many('account.journal', string='Journals', check_company=True)

    def button_export_html(self):
        return self._print_report(report_type='html')

    def button_export_pdf(self):
        return self._print_report(report_type='pdf')

    def button_export_xlsx(self):
        return self._print_report(report_type='xlsx')

    def _print_report(self, report_type):
        self.ensure_one()

        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to), ('company_id', '=', self.company_id.id)]

        if self.target_move == 'posted':
            domain.append(('state', '=', 'posted'))

        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))

        return self.env.ref(f'trilab_pl_reports.action_print_report_pl_journal_{report_type}').report_action(
            self.env['account.move'].search(domain)
        )

    def get_print_report_name(self, prefix='pl_journal'):
        return f'{prefix}_{self.date_from:%m_%Y}'


class JournalReportPL(models.TransientModel):
    _name = 'report.trilab_pl_reports.pl_journal_report'
    _inherit = ['jpk.trilab.export_helper']
    _description = 'PL Journal Report'

    columns = [
        CellDefinition(None, 'Numer zapisu'),
        CellDefinition(None, 'Data zapisu', 'date'),
        CellDefinition(None, 'Księgował'),
        CellDefinition(None, 'Dokument'),
        CellDefinition(None, 'Data księgowania', 'date'),
        CellDefinition(None, 'Dziennik'),
        CellDefinition(None, 'Opis operacji', style='text_wrap'),
        CellDefinition(None, 'Treść zapisu', style='text_wrap'),
        CellDefinition(None, 'Konto'),
        CellDefinition(None, 'Nazwa konta'),
        CellDefinition(None, 'Kwota Winien', 'float', 'pln_currency'),
        CellDefinition(None, 'Kwota Ma', 'float', 'pln_currency'),
    ]

    xlsx_styles = {
        'default': {'font_size': 12},
        'text_wrap': {'font_size': 12, 'text_wrap': True},
        'pln_currency': {'font_size': 12, 'num_format': '# ##0.00 [$zł-415]'},
        'title': {'bold': True, 'bottom': 2},
    }

    def _get_report_values(self, docids, data):
        docs = self.env['account.move'].browse(docids).sorted(lambda move_id: (move_id.date, move_id.name, move_id.id))
        company = docs.mapped('company_id')

        return {
            'doc_ids': docids,
            'doc_model': self.env['account.move'],
            'company_name': company.display_name,
            'currency_id': company.currency_id,
            'docs': docs,
        }

    @api.model
    def _get_report_name(self):
        return _('Journal Report')

    @api.model
    def _get_report_data(self, docids, options):
        move_ids = self.env['account.move'].browse(docids).sorted(lambda mov_id: (mov_id.date, mov_id.id))
        table_rows = []

        for move_index, move_id in enumerate(move_ids, start=1):
            for line_id in move_id.line_ids.sorted(lambda lin_id: (lin_id.create_date, lin_id.id)):
                table_rows.append(
                    [
                        move_index,
                        line_id.date,
                        line_id.write_uid.name,
                        move_id.name,
                        line_id.date,
                        line_id.journal_id.name,
                        line_id.ref,
                        line_id.name,
                        line_id.account_id.code,
                        line_id.account_id.name,
                        line_id.debit,
                        line_id.credit,
                    ]
                )

        return table_rows

    def generate_xlsx_report(self, workbook, doc_ids, options):
        sheet = workbook.add_worksheet(self._get_report_name())

        max_widths = []
        columns = []

        for col_idx, field in enumerate(self.columns):
            self._write_cell(sheet, 0, col_idx, field.name, style='title')

        for y, row in enumerate(self._get_report_data(doc_ids, options), start=1):
            if not columns:
                columns = self.columns

            if not max_widths:
                max_widths = [0] * len(row)

            for x, value in enumerate(row):
                self._write_cell(sheet, y, x, value, definition=columns[x] if x < len(columns) else None)
                max_widths[x] = max(max_widths[x], len(str(value)))

        for x, width in enumerate(max_widths):
            sheet.set_column(x, x, min(35, width + 10))
