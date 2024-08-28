# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Set advanced fields
    integration_ids = env['sale.integration'].search([])
    integration_ids._set_default_advanced_fields()

    # 2. Update the `validate_barcode` field
    for integration in integration_ids.filtered(lambda x: x.type_api in ['magento2', 'woocommerce']):
        integration.validate_barcode = False
