import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

VERSION = '18.0.1.1.2'
MODULE = 'trilab_ksef'


def migrate(cr, version):
    _logger.info(f'post migration {VERSION} start (from {version})')

    env = api.Environment(cr, SUPERUSER_ID, {})

    for company_id in env['res.company'].search([('x_ksef_token', '!=', False)]):
        company_id.x_ksef_token = company_id._x_ksef_secret_encrypt(company_id.x_ksef_token)

    _logger.info(f'post migration {VERSION} finished')
