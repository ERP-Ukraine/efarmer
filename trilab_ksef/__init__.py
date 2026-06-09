from cryptography.fernet import Fernet

from . import models, report, wizard


def post_init(env):
    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, Fernet.generate_key().decode())


def uninstall(env):
    # noinspection PyTypeChecker
    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, None)
