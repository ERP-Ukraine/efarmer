import logging

from odoo import SUPERUSER_ID, api
from odoo.addons.trilab_ksef import models, post_init

_logger = logging.getLogger(__name__)

VERSION = '18.0.1.1.2'
MODULE = 'trilab_ksef'


def migrate(cr, version):
    _logger.info(f'pre migration {VERSION} start (from {version})')

    env = api.Environment(cr, SUPERUSER_ID, {})

    if not env['ir.config_parameter'].get_param(models.res_company.ENC_KEY):
        post_init(env)

    _logger.info(f'pre migration {VERSION} finished')
