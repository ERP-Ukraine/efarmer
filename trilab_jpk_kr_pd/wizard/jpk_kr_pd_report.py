from odoo import api, fields, models


class JpkKrPdReportWizard(models.TransientModel):
    _name = 'jpk.kr.pd.report.wizard'
    _description = 'JPK KR PD Report Wizard'

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    date_from = fields.Date('Start Date', default=lambda self: fields.Date.start_of(fields.Date.today(), 'year'))
    date_to = fields.Date('End Date', default=lambda self: fields.Date.end_of(fields.Date.today(), 'year'))
    is_jpk_transfer_installed = fields.Boolean(compute='_compute_jpk_transfer')
    purpose_type = fields.Selection([('1', 'Submission'), ('2', 'Correction')], 'Purpose Type', default='1')
    zois_type = fields.Selection(
        [(val, val) for val in ['ZOiS1', 'ZOiS2', 'ZOiS3', 'ZOiS4', 'ZOiS5', 'ZOiS6', 'ZOiS7', 'ZOiS8']],
        'ZOiS Type',
        required=True,
        default='ZOiS7',
        help=(
            'ZOiS1 - Banks trial balance\n'
            'ZOiS2 - Insurance and reinsurance companies trial balance\n'
            'ZOiS3 - Public benefit and volunteer organizations trial balance\n'
            'ZOiS4 - Investment funds trial balance\n'
            'ZOiS5 - Brokerage houses trial balance\n'
            'ZOiS6 - SKOK trial balance\n'
            'ZOiS7 - Other entities trial balance\n'
            'ZOiS8 - Entities applying IFRS trial balance'
        ),
    )

    @api.depends('company_id')
    def _compute_jpk_transfer(self):
        for wizard_id in self:
            wizard_id.is_jpk_transfer_installed = wizard_id.company_id.x_is_jpk_transfer_installed()

    def _export(self, report_type):
        """Default export is PDF."""
        self.ensure_one()

        return self._print_report(report_type)

    def _prepare_report_data(self):
        self.ensure_one()

        return {
            'wizard_id': self.id,
            'company_id': self.company_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'lang': self.env.ref('base.lang_pl').code,
            'purpose_type': self.purpose_type,
            'zois_type': self.zois_type,
        }

    def _print_report(self, report_type):
        self.ensure_one()

        report_name = 'trilab_jpk_kr_pd.jpk_kr_pd_report'
        data = self._prepare_report_data()

        if report_type == 'jpk_transfer':
            # noinspection PyUnresolvedReferences
            return self.env[f'report.{report_name}'].transfer_xml(data)

        return (
            self.env['ir.actions.report']
            .search(domain=[('report_name', '=', report_name), ('report_type', '=', report_type)], limit=1)
            .report_action([], data=data)
        )

    def button_export_html(self):
        return self._export(report_type='qweb-html')

    def button_export_xlsx(self):
        return self._export(report_type='jpk_xlsx')

    def button_export_xml(self):
        return self._export(report_type='jpk_xml')

    def button_transfer_xml(self):
        return self._export(report_type='jpk_transfer')
