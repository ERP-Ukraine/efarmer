import logging
from cryptography.fernet import Fernet

from . import models, report, wizard


_logger = logging.getLogger(__name__)


def pre_init(env):
    # alter table account_move drop column x_ksef_invoice_status;
    env.cr.execute("""
ALTER TABLE account_move
ADD COLUMN x_ksef_invoice_status VARCHAR(255);
    """)

    # alter table account_tax drop column x_ksef_amount;
    env.cr.execute("""
ALTER TABLE account_tax
ADD COLUMN x_ksef_amount VARCHAR(255);
    """)


def post_init(env):
    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, Fernet.generate_key().decode())

    step = 200
    for i in range(0, env['account.move'].search_count([]), step):
        _logger.info(f"account.move: run _x_ksef_compute_invoice_status for range {i} - {i + step}")
        env['account.move'].search([], limit=step, offset=i, order="id asc")._x_ksef_compute_invoice_status()
        env.cr.commit()
        env['account.move'].invalidate_model()

    for i in range(0, env['account.tax'].search_count([]), step):
        _logger.info(f"account.tax: run _x_ksef_compute_amount for range {i} - {i + step}")
        env['account.tax'].search([], limit=step, offset=i, order="id asc")._x_ksef_compute_amount()
        env.cr.commit()
        env['account.tax'].invalidate_model()


def uninstall(env):
    # noinspection PyTypeChecker
    env['ir.config_parameter'].set_param(models.res_company.ENC_KEY, None)
