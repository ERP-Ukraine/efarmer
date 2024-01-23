# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    integrations = env['sale.integration'].search([('state', '=', 'active')])

    for integration in integrations:
        integration.action_active()
