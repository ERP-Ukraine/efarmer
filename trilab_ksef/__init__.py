from cryptography.fernet import Fernet

from odoo import SUPERUSER_ID, api

from . import models, report, wizard


def post_init(cr, _registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, Fernet.generate_key().decode())


def uninstall(cr, _registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # noinspection PyTypeChecker
    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, None)
