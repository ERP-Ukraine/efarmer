# See LICENSE file for full copyright and licensing details.

from . import patch
from . import models
from . import wizard
from . import controllers

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """ Generate API key for the installed integration. """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Config = env['res.config.settings']
    Config.generate_integration_api_key()
