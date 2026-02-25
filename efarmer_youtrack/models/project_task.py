# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class Task(models.Model):
    _inherit = "project.task"

    youtrack_id = fields.Char(
        string="YouTrack ID",
    )

    task_code = fields.Char(
        string="Issue Code",
    )

    product_version_id = fields.Many2one(
        comodel_name="youtrack.product.version",
        string="Product Version",
    )

    issue_type_id = fields.Many2one(
        comodel_name="youtrack.issue.type",
        string="Issue Type",
    )

    name_pl = fields.Char(
        string="Name PL",
    )

    is_epic = fields.Boolean(
        string="Is Epic",
        default=False,
        readonly=True,
    )

    epic_id = fields.Many2one(
        comodel_name="project.task",
        string="Epic Task",
        readonly=True,
    )

    asset_id = fields.Many2one(
        comodel_name="account.asset",
        string="Product",
    )
