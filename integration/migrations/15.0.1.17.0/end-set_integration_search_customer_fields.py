# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Set search customer fields
    integration_ids = env['sale.integration'].search([])
    for integration in integration_ids:
        integration.write({
            'search_customer_fields_ids': integration._default_search_customer_fields_ids(),
        })
