from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # Generate API key to use for API requests from designer to Odoo.
    env = api.Environment(cr, SUPERUSER_ID, {})
    Config = env['res.config.settings']
    Config.generate_zld_api_key()
