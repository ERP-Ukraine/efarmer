# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Generate API key for the installed integration.
    Config = env['res.config.settings']
    Config.generate_integration_api_key()
