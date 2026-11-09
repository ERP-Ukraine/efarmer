from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    Generate a new API key on upgrade.

    The designer has to be connected again with the new key. Printing does not use the key.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.config.settings'].generate_zld_api_key()
