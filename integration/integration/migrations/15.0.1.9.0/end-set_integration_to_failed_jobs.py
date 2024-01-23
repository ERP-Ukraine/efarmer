# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    jobs = env['queue.job'].search([
        ('state', '=', 'failed'),
        ('integration_id', '=', False),
    ])
    jobs._set_integration()
