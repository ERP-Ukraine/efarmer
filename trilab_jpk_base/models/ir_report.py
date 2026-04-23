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
        report_model_name = f'report.{report_sudo_id.report_name}'
        report_model_id = self.env[report_model_name]
        return (
            report_model_id.with_context(active_model=report_sudo_id.model).sudo(False).create_xlsx_report(docids, data)  # noqa
        )

    @api.model
    def _render_jpk_xml(self, report_ref, docids, data):
        report_sudo_id = self._get_report(report_ref)
        report_model_name = f'report.{report_sudo_id.report_name}'
        report_model_id = self.env[report_model_name]
        return (
            report_model_id.with_context(active_model=report_sudo_id.model).sudo(False).create_xml_report(docids, data)  # noqa
        )

    @api.model
    def _get_report_from_name(self, report_name):
        res = super()._get_report_from_name(report_name)

        if res:
            return res

        return (
            self.env['ir.actions.report']
            .with_context(**self.env['res.users'].context_get())
            .search([('report_type', '=', 'jpk_xlsx'), ('report_name', '=', report_name)], limit=1)
        )
