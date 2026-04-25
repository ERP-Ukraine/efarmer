import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

REMOVE_MODELS = [
    'account.report.expression',
    'account.report.line',
    'account.report.column',
    'account.report',
]


# noinspection PyUnusedLocal
def migrate(cr, version):
    _logger.info(f'Start migration 18.0.1.0.0 from {version} - pre recreate reports')

    _logger.info('remove assignment of depreciated account tags')

    for model in REMOVE_MODELS:
        _logger.info(f'cleanup {model=}')
        table = model.replace('.', '_')
        cr.execute(
            SQL("""DELETE FROM %s WHERE id in
             (SELECT res_id FROM ir_model_data WHERE module = 'trilab_pl_reports' and name = %s)""",
                SQL.identifier(table), model))
        cr.execute(
            SQL("""DELETE FROM ir_model_data WHERE module = 'trilab_pl_reports' and name = %s""", model)
        )

    _logger.info('pre migration 18.0.1.0.0 finished')
