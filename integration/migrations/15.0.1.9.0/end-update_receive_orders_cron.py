# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    integration_ids = env['sale.integration'].with_context(active_test=False).search([])

    for integration in integration_ids:
        vals = {
            'name': f'Integration: {integration.name} [{integration.id}] Receive Orders',
            'code': f'model.browse({integration.id}).integration_receive_orders_cron()',
        }
        cron = integration.receive_orders_cron_id
        cron.write(vals)
