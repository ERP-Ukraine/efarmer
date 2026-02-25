# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class YoutrackIssueType(models.Model):
    _name = "youtrack.issue.type"
    _description = "YouTrack Issue Type"

    name = fields.Char(
        string="Name",
    )

    youtrack_id = fields.Char(
        string="Youtrack ID",
        readonly=True,
    )
