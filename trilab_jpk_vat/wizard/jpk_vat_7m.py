import base64

from odoo import _, api, fields, models
from odoo.addons.web.controllers.utils import clean_action


class JpkVAT7MReportWizard(models.TransientModel):
    _name = 'jpk.vat7m.report.wizard'
    _description = 'JPK VAT 7M Report Wizard'

    company_id = fields.Many2one(
        comodel_name='res.company', default=lambda self: self.env.company.id, required=False, string='Company'
    )

    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    target_move = fields.Selection(
        [('posted', 'All Posted Entries'), ('all', 'All Entries')],
        string='Target Moves',
        required=True,
        default='posted',
    )
    submit_purpose = fields.Selection(
        [('1', 'New Declaration'), ('2', 'Correction')], string='Submit Purpose', required=True, default='1'
    )

    is_pl_partner_sync_installed = fields.Boolean(compute='_compute_is_pl_partner_sync_installed')

    @api.depends('date_from')
    def _compute_is_pl_partner_sync_installed(self):
        self.is_pl_partner_sync_installed = (
            self.env['ir.module.module']._get('trilab_pl_partners_sync').state == 'installed'
        )

    def button_export_html(self):
        return self._export(report_type='qweb-html')

    def button_export_pdf(self):
        return self._export(report_type='qweb-pdf')

    def button_export_xlsx(self):
        return self._export(report_type='xlsx')

    def button_export_xlsx_flat(self):
        return self._export(report_type='xlsx-flat')

    def button_export_xml(self):
        return self._export(report_type='xml')

    def button_export_xml_eu(self):
        return self._export(report_type='xml-ue')

    def _print_report(self, report_type):
        self.ensure_one()
        data = self._prepare_vat_report()
        report_name = 'trilab_jpk_vat.jpk_vat7m_report'

        if report_type == 'xlsx':
            return {
                'type': 'ir.actions.report',
                'report_name': report_name,
                'report_type': 'jpk_xlsx',
                'report_file': 'trilab_jpk_vat.jpk_vat7m_report',
                'name': 'VAT 7M',
                'data': data,
            }
        elif report_type == 'xlsx-flat':
            return {
                'type': 'ir.actions.report',
                'report_name': report_name,
                'report_type': 'jpk_xlsx',
                'report_file': 'trilab_jpk_vat.jpk_vat7m_report',
                'name': 'VAT 7M',
                'data': data,
                'context': {'x_flat': True},
            }

        elif report_type == 'xml':
            v7m_report = self._create_jpk_vat7m_report(data)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'jpk.vat.7m',
                'name': 'JPK VAT 7M',
                'res_id': v7m_report.id,
                'target': 'new',
                'view_mode': 'form',
                'context': {'form_view_initial_mode': 'edit'},
            }
        elif report_type == 'xml-ue':
            vat_eu_report = self._create_jpk_vat_ue_report(data)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'jpk.vat.ue',
                'name': 'JPK VAT UE',
                'res_id': vat_eu_report.id,
                'target': 'new',
                'view_mode': 'form',
                'context': {'form_view_initial_mode': 'edit'},
            }

        return (
            self.env['ir.actions.report']
            .search([('report_name', '=', report_name), ('report_type', '=', report_type)], limit=1)
            .report_action(self, data=data)
        )

    def _create_jpk_vat7m_report(self, data):
        report_date = fields.Date.to_date(data['date_from'])

        xml, sums = self.env['report.trilab_jpk_vat.jpk_vat7m_report'].get_xml_extended(data)

        sums = {k.lower(): v for k, v in sums.items()}

        return self.env['jpk.vat.7m'].create(
            {
                'version': '1-2E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': int(data.get('submit_purpose', 1)),
                'document_type_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
                'source_xml': base64.b64encode(xml),
                **sums,
            }
        )

    def _create_jpk_vat_ue_report(self, data):
        report_date = fields.Date.to_date(data['date_from'])

        xml, sums = self.env['report.trilab_jpk_vat.jpk_vat_eu_report'].get_xml_extended(data)

        sums = {k.lower(): v for k, v in sums.items()}

        return self.env['jpk.vat.ue'].create(
            {
                'version': '2-0E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': int(data.get('submit_purpose', 1)),
                'source_xml': base64.b64encode(xml),
                'group_line_ids': [
                    fields.Command.create(
                        {
                            'country_code': val.get('country_code'),
                            'nip': val.get('vat'),
                            'amount': val.get('amount'),
                            'tt': val.get('tt'),
                            'group': group.lower(),
                        }
                    )
                    for group, vals in sums.items()
                    for val in vals
                ],
            }
        )

    def _prepare_vat_report(self):
        self.ensure_one()
        return {
            'wizard_id': self.id,
            'company_id': self.company_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'only_posted_moves': self.target_move == 'posted',
            'submit_purpose': int(self.submit_purpose),
            'account_financial_report_lang': self.env.lang,
        }

    def _export(self, report_type):
        """Default export is PDF."""
        self.ensure_one()
        return self._print_report(report_type)

    def get_print_report_name(self, prefix='vat_7m'):
        return f'{prefix}_{self.date_from:%m_%Y}{self.submit_purpose == "2" and "_korekta" or ""}'

    def button_check_partners_vat(self):
        self.ensure_one()
        # works only with trilab_pl_partners_sync installed

        params = {
            'jpk_doc_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
            'journal_types': ('sale', 'purchase'),
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company': self.company_id.id,
            'allowed_states': ('posted',) if self.target_move == 'posted' else ('posted', 'draft'),
        }

        self.env.cr.execute(self.env['report.trilab_jpk_vat.jpk_vat7m_report']._get_query(), params)

        partner_ids = self.env['res.partner'].browse({_l['partnerid'] for _l in self.env.cr.dictfetchall()})

        # noinspection PyUnresolvedReferences
        errors = partner_ids.x_pl_check_mf_nip_wl(raise_exception=False, post_change=False)

        # noinspection PyUnresolvedReferences
        wizard_id = self.env['trilab.check.partner'].create(
            {
                'check_ids': [
                    fields.Command.create(
                        {
                            'partner_id': partner_id,
                            'error_type': error.get('error_type'),
                            'error_message': error.get('error_message'),
                        }
                    )
                    for partner_id, error in errors.items()
                ],
                'mode': 'nip',
            }
        )

        partner_ids -= self.env['res.partner'].browse(errors.keys())

        wizard_id.check_ids = [
            fields.Command.create(
                {
                    'partner_id': partner_id.id,
                    'error_type': error_type,
                    'error_message': error_message,
                }
            )
            for nip_state, error_type, error_message in (
                ('N', 'not_registered_nip', _('Not registered NIP')),
                ('Z', 'vat_exempt_nip', _('VAT exempt NIP')),
            )
            for partner_id in partner_ids.filtered(lambda _p_id: _p_id.x_pl_nip_state == nip_state)
        ]

        action = clean_action(
            action=partner_ids._x_pl_check_action(record_id=wizard_id.id, title=_('MF VAT Validation Results')),
            env=self.env,
        )
        action.setdefault('context', {})
        action['context']['x_hide_buttons'] = True

        return action
