import logging

_logger = logging.getLogger(__name__)

RENAME_COLUMNS = {
    'res_partner': {
        'nip_state': 'x_pl_nip_state',
        'vies_state': 'x_pl_vies_state',
        'vies_check_date': 'x_pl_vies_check_date',
        'nip_check_date': 'x_pl_nip_check_date',
        'gus_update_date': 'x_pl_gus_update_date',
    },
    'res_company': {'krd_env': 'x_pl_krd_env', 'krd_login': 'x_pl_krd_login', 'krd_pass': 'x_pl_krd_pass'},
}

RENAME_PARAMETERS = [('trilab_gusregon.gus_api_key', 'trilab_gusregon.x_pl_gus_api_key')]

REMOVE_TABLES = [('res_partner_res_partner_check_nip_rel', None), ('res_partner_check_nip', 'res.partner.check.nip')]


# noinspection PyUnusedLocal
def migrate(cr, version):
    with cr.savepoint():
        for table in RENAME_COLUMNS:
            cr.execute('SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s', (table,))
            table_columns = [r['column_name'] for r in cr.dictfetchall()]

            for column_from, column_to in RENAME_COLUMNS[table].items():
                if column_from in table_columns and column_to not in table_columns:
                    _logger.info(f'renaming column {column_from} to {column_to} for table {table}')
                    cr.execute(f'''ALTER TABLE "{table}" RENAME COLUMN "{column_from}" TO "{column_to}"''')
                    cr.execute('UPDATE ir_model_fields SET name = %s WHERE name = %s', (column_to, column_from))
                else:
                    _logger.info(f'renaming column {column_from} to {column_to} for table {table} - no change needed')

        for param_from, param_to in RENAME_PARAMETERS:
            _logger.info(f'rename config parameter "{param_from}" to "{param_to}"')
            cr.execute('UPDATE ir_config_parameter SET key = %s WHERE key = %s', (param_to, param_from))

        for db_table, table in REMOVE_TABLES:
            # remove table from the db
            cr.execute('SELECT table_name FROM information_schema.tables where table_name = %s', (db_table,))
            if cr.dictfetchall():
                _logger.info(f'removing table {db_table}')
                cr.execute(f'DROP TABLE {db_table}')

            # remove table from the odoo
            if not table:
                continue

            _logger.debug('checking odoo registry')
            cr.execute('SELECT id FROM ir_model WHERE model = %s', (table,))
            model = cr.dictfetchone()

            if not model:
                continue

            _logger.debug(f'removing model {table}({model["id"]}) from odoo registry')
            cr.execute('DELETE FROM ir_model_relation WHERE model = %(id)s', model)
            cr.execute('DELETE FROM ir_model WHERE id = %(id)s', model)

        _logger.info('removing old actions')
        cr.execute('DELETE FROM ir_act_window WHERE res_model = %s', ('res.partner.check.nip',))

    _logger.info('migration finished')
