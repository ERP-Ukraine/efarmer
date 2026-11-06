from odoo import api, fields, models


class ReportAction(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection(
        selection_add=[('jpk_xlsx', 'JPK XLSX'), ('jpk_xml', 'JPK XML')],
        ondelete={'jpk_xlsx': 'set default', 'jpk_xml': 'set default'},
    )

    @api.model
    def _render_jpk_xlsx(self, report_ref, docids, data):
        report_sudo_id = self._get_report(report_ref)

        # noinspection PyUnresolvedReferences
        return (
            self.env[f'report.{report_sudo_id.report_name}']
            .with_context(active_model=report_sudo_id.model)
            .sudo(False)
            .create_xlsx_report(docids, data)
        )

    @api.model
    def _render_jpk_xml(self, report_ref, docids, data):
        report_sudo_id = self._get_report(report_ref)

        # noinspection PyUnresolvedReferences
        return (
            self.env[f'report.{report_sudo_id.report_name}']
            .with_context(active_model=report_sudo_id.model)
            .sudo(False)
            .create_xml_report(docids, data)
        )
