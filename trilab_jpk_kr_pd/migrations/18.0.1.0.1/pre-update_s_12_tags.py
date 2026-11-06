import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(f'Pre update_s_12_tags start (from {version})')

    with cr.savepoint():
        if column_exists(cr, 'account_account', 'x_s_12_1_tag'):
            _logger.info('Replacing "other" with "INNE" in x_s_12_1_tag')

            cr.execute("""
                       UPDATE account_account
                       SET x_s_12_1_tag = 'INNE'
                       WHERE x_s_12_1_tag = 'other'
                       """)

        if column_exists(cr, 'account_account', 'x_s_12_2_tag'):
            _logger.info('Replacing "other" with "INNE" in x_s_12_2_tag')

            cr.execute("""
                       UPDATE account_account
                       SET x_s_12_2_tag = 'INNE'
                       WHERE x_s_12_2_tag = 'other'
                       """)

    _logger.info('Pre update_s_12_tags finished')
