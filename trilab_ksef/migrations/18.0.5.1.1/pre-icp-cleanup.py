import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(f'Start migration from {version} - pre icp cleanup')

    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key LIKE 'ksef_invoice_batch_import_state_%'
           OR key LIKE 'ksef_invoice_batch_import_queue_%'""")

    _logger.info(f'Finished migration from {version} - pre icp cleanup')
