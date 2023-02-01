from odoo import fields, models


class YoutrackIssueType(models.Model):
    _name = 'youtrack.issue.type'
    _description = 'YouTrack Issue Type'

    name = fields.Char(
        string='Name',
    )

    youtrack_id = fields.Char(
        string='Youtrack ID',
        readonly=True,
    )
