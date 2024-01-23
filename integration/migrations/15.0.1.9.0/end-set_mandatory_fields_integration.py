# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Set mandatory fields for the installed integration.
    integrations = env['sale.integration'].search([])
    for integration in integrations:
        integration.write({
            'mandatory_fields_initial_product_export': integration._get_default_mandatory_fields(),
        })
