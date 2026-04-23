import logging

_logger = logging.getLogger(__name__)

REMOVE_TAGS = [
    'RZiSPor_H_IV',
    'RZiSKalk_J_V',
    'RZiSKalk_K_IV',
    'RZiSPor_G_V',
    'RZiSPor_H_IV',
]


# noinspection PyUnusedLocal
def migrate(cr, version):
    _logger.info(f'Start migration 17.0.0.0.0 from {version} - pre rename')

    with cr.savepoint():
        _logger.info('remove assignment of depreciated account tags')
        with cr.savepoint():
            cr.execute(
                "SELECT id, res_id from ir_model_data WHERE module = 'trilab_pl_reports' and name = ANY(%s)",
                (REMOVE_TAGS,),
            )

            for row in cr.fetchall():
                cr.execute('DELETE FROM account_account_account_tag WHERE account_account_tag_id = %s', (row[1],))
                cr.execute('DELETE FROM ir_model_data WHERE id = %s', (row[0],))

    _logger.info('pre migration finished')
