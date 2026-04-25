import logging

_logger = logging.getLogger(__name__)

RENAME_COLUMNS = {
    'account_move': (('x_refund_invoice_id', 'reversed_entry_id'), ('refund_invoice_id', 'reversed_entry_id')),
    'account_move_line': (('corrected_line', 'x_is_corrected_line'),),
}


# noinspection PyUnusedLocal
def migrate(cr, version):
    _logger.info(f'Start migration 16.0.0 from {version} - pre rename')

    with cr.savepoint():
        for table in RENAME_COLUMNS:
            cr.execute('SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s', (table,))
            table_columns = [r['column_name'] for r in cr.dictfetchall()]

            if table == 'account_move':
                if 'refund_invoice_id' in table_columns:
                    cr.execute(
                        """UPDATE account_move SET reversed_entry_id = refund_invoice_id
                    WHERE reversed_entry_id is null or reversed_entry_id != refund_invoice_id """
                    )
                    _logger.info(f'UPDATE account_move refund_invoice_id -> reversed_entry_id (updated {cr.rowcount})')

                if 'x_refund_invoice_id' in table_columns:
                    cr.execute(
                        """UPDATE account_move SET reversed_entry_id = x_refund_invoice_id
                    WHERE reversed_entry_id is null or reversed_entry_id != x_refund_invoice_id """
                    )
                    _logger.info(f'UPDATE account_move reversed_entry_id -> reversed_entry_id (updated {cr.rowcount})')

            for column_from, column_to in RENAME_COLUMNS[table]:
                if column_from in table_columns and column_to not in table_columns:
                    _logger.info(f'renaming column {column_from} to {column_to} for table {table}')
                    cr.execute(f'''ALTER TABLE "{table}" RENAME COLUMN "{column_from}" TO "{column_to}"''')
                    cr.execute('UPDATE ir_model_fields SET name = %s WHERE name = %s', (column_to, column_from))
                else:
                    _logger.info(f'renaming column {column_from} to {column_to} for table {table} - no change needed')

    _logger.info('migration finished')
