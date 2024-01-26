# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    integration_ids = env['sale.integration'].with_context(active_test=False).search([
        ('type_api', '=', 'magento2'),
    ])
    job_kwargs = {
        'description': 'Re Import Sale Order Statuses',
    }
    for integration in integration_ids:
        integration.with_delay(**job_kwargs).integrationApiImportSaleOrderStatuses()
