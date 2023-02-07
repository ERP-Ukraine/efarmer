# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    youtrack_id = fields.Char(
        string='YouTrack ID',
    )

    work_type_id = fields.Many2one(
        comodel_name='youtrack.work.type',
        string='Work Type',
    )
