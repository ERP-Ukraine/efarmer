import logging

from odoo.tools import SQL
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(f'post migrate_s_12_tags start (from {version})')

    with cr.savepoint():
        for column, prefix in (('x_s_12_1_tag', 'S_12_1'), ('x_s_12_2_tag', 'S_12_2')):
            if not column_exists(cr, 'account_account', column):
                continue

            _logger.info(f'migrating {column} value to account tag')

            cr.execute(
                SQL(
                    """
                    INSERT INTO account_account_account_tag (account_account_id, account_account_tag_id)
                    SELECT aa.id, aat.id
                    FROM account_account AS aa
                             JOIN account_account_tag AS aat
                                  ON aat.name ->> 'en_US' = %(prefix)s || aa.%(column)s
                                      AND aat.applicability = 'accounts'
                    WHERE aa.%(column)s IS NOT NULL
                      AND NOT EXISTS (SELECT 1
                                      FROM account_account_account_tag AS aaat
                                               JOIN account_account_tag AS existing_aat
                                                    ON existing_aat.id = aaat.account_account_tag_id
                                      WHERE aaat.account_account_id = aa.id
                                        AND starts_with(existing_aat.name ->> 'en_US', %(prefix)s))
                    """,
                    prefix=f'{prefix}__',
                    column=SQL.identifier(column),
                )
            )

    _logger.info('post migrate_s_12_tags finished')
