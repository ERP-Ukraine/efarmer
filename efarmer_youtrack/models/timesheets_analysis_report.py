from odoo import fields, models


class TimesheetsAnalysisReport(models.Model):
    _inherit = "timesheets.analysis.report"

    work_type_id = fields.Many2one(
        "youtrack.work.type", string="Work Type", readonly=True
    )

    def _select(self):
        return super()._select() + """,
            A.work_type_id AS work_type_id"""

    def _group_by(self):
        return super()._group_by() + """,
            A.work_type_id"""
