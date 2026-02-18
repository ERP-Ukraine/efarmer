# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    notify_failed_jobs = fields.Boolean(
        string='Failed Job Notifications',
        default=True,
        help=(
            'Enable this option if you want to receive notifications when a job fails. '
            'You must also have "Job Queue Manager" access rights to actually receive these notifications.'
        ),
        index=True,
    )
