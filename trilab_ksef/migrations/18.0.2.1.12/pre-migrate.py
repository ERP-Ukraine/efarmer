import logging

from odoo.tools import SQL
from odoo.tools.sql import table_columns

_logger = logging.getLogger(__name__)

VERSION = '18.0.2.1.12'
MODULE = 'trilab_ksef'


def migrate(cr, version):
    _logger.info(f'pre migration {VERSION} start (from {version})')

    tablename = 'res_partner'
    columnname = 'x_ksef_purchase_journal_id'
    update_columnname = '_x_ksef_purchase_journal_id_upg'

    columns = table_columns(cr, tablename)

    if columnname in columns and columns[columnname]['udt_name'].startswith('int'):
        cr.execute(
            SQL(
                'UPDATE ir_model_fields SET company_dependent = TRUE WHERE model = %s AND name = %s RETURNING id',
                'res.partner',
                columnname,
            )
        )
        [field_id] = cr.fetchone()

        cr.execute(
            SQL(
                'ALTER TABLE %s RENAME COLUMN %s TO %s',
                SQL.identifier(tablename),
                SQL.identifier(columnname),
                SQL.identifier(update_columnname),
            )
        )

        cr.execute(SQL('ALTER TABLE %s ADD COLUMN %s jsonb', SQL.identifier(tablename), SQL.identifier(columnname)))

        cr.execute(
            SQL(
                """UPDATE %(table)s SET %(column)s = jsonb_build_object(%(company_colum)s, %(tmp_column)s)
                   WHERE %(column)s IS NOT NULL AND %(company_colum)s IS NOT NULL""",
                table=SQL.identifier(tablename),
                column=SQL.identifier(columnname),
                tmp_column=SQL.identifier(update_columnname),
                company_colum=SQL.identifier('company_id'),
            )
        )

        cr.execute(
            SQL('ALTER TABLE %s DROP COLUMN %s CASCADE', SQL.identifier(tablename), SQL.identifier(update_columnname))
        )

        cr.execute('DELETE FROM ir_default WHERE field_id = %s', [field_id])

    _logger.info(f'pre migration {VERSION} finished')
