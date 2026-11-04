# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    The webhook shop domain check compares the `X-Shopify-Shop-Domain` header with `original_url`,
    but only Test Connection and reactivation filled it, so older integrations may reject every webhook.

    Queue one job per active integration to fill it. Shopify is asked from the job, never from the
    migration: a failing request here would stop the upgrade.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    integrations = env['sale.integration'].search([
        ('type_api', '=', 'shopify'),
        ('state', '=', 'active'),
    ])

    for integration in integrations.filtered(lambda x: not x.get_settings_value('original_url')):
        integration.with_context(
            company_id=integration.company_id.id,
            job_integration_id=integration.id,
        ).with_delay(
            priority=12,
            description=f'{integration.name}: Fill Original Shop ID',
            identity_key=f'fill_original_url-{integration.type_api}_{integration.id}',
        ).fill_original_url()
