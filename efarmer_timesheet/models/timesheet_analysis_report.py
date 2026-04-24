# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class TimesheetAnalysisReport(models.Model):
    _inherit = "timesheets.analysis.report"

    task_product_id = fields.Many2one(
        "account.asset",
        string="Task Asset",
        readonly=True,
    )

    epic_id = fields.Many2one(
        "project.task",
        string="Epic Task",
        readonly=True,
    )

    name_pl = fields.Char(
        string="Name PL",
        readonly=True,
    )

    product_version_id = fields.Many2one(
        "youtrack.product.version",
        string="Product Version",
        readonly=True,
    )

    issue_type_id = fields.Many2one(
        "youtrack.issue.type",
        string="Issue Type",
        readonly=True,
    )

    def _from(self):
        return super()._from() + """
            LEFT JOIN project_task task ON task.id = A.task_id
        """

    def _select(self):
        return super()._select() + """
            , task.asset_id as task_product_id
            , task.epic_id as epic_id
            , task.name_pl as name_pl
            , task.product_version_id as product_version_id
            , task.issue_type_id as issue_type_id
        """

    def _group_by(self):
        return super()._group_by() + """
            , task.asset_id
            , task.epic_id
            , task.name_pl
            , task.product_version_id
            , task.issue_type_id
        """
