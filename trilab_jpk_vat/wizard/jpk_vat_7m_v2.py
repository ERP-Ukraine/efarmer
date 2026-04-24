import base64

from odoo import fields, models


class JpkVAT7MReportWizard(models.TransientModel):
    _name = 'jpk.vat7m.v2.report.wizard'
    _description = 'JPK VAT 7M V2 Report Wizard'
    _inherit = 'jpk.vat7m.report.wizard'

    def _print_report(self, report_type):
        self.ensure_one()
        data = self._prepare_vat_report()
        report_name = 'trilab_jpk_vat.jpk_vat7m_v2_report'

        if report_type == 'xlsx':
            return {
                'type': 'ir.actions.report',
                'report_name': report_name,
                'report_type': 'jpk_xlsx',
                'report_file': 'trilab_jpk_vat.jpk_vat7m_v2_report',
                'name': 'VAT 7M 1-0E',
                'data': data,
            }
        elif report_type == 'xlsx-flat':
            return {
                'type': 'ir.actions.report',
                'report_name': report_name,
                'report_type': 'jpk_xlsx',
                'report_file': 'trilab_jpk_vat.jpk_vat7m_v2_report',
                'name': 'VAT 7M 1-0E',
                'data': data,
                'context': {'x_flat': True},
            }
        elif report_type == 'xml':
            v7m_report = self._create_jpk_vat7m_report(data)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'jpk.vat.7m',
                'name': 'JPK VAT 7M 1-0E',
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

        xml, sums = self.env['report.trilab_jpk_vat.jpk_vat7m_v2_report'].get_xml_extended(data)

        sums = {k.lower(): v for k, v in sums.items()}

        return self.env['jpk.vat.7m'].create(
            {
                'version': '1-0E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': int(data.get('submit_purpose', 1)),
                'document_type_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_0_doc_type').id,
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
                'document_type_id': self.env.ref('trilab_jpk_base.vat_ue5_v2_0e_doc_type').id,
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

    def get_print_report_name(self, prefix='vat_7m_v2'):
        return f'{prefix}_{self.date_from:%m_%Y}{self.submit_purpose == "2" and "_korekta" or ""}'
