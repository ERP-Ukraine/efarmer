from odoo import fields, models


class YoutrackProductVersion(models.Model):
    _name = 'youtrack.product.version'
    _description = 'YouTrack Product Version'

    name = fields.Char(
        string='Name',
    )

    youtrack_id = fields.Char(
        string='Youtrack ID',
        readonly=True,
    )
