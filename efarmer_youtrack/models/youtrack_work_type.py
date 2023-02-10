# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class YoutrackWorkType(models.Model):
    _name = 'youtrack.work.type'
    _description = 'YouTrack Work Type'

    name = fields.Char(
        string='Name',
    )

    youtrack_id = fields.Char(
        string='Youtrack ID',
        readonly=True,
    )
