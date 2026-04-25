import logging

_logger = logging.getLogger(__name__)


REMOVE_ACTIONS = ['trilab_pl_partners_sync.check_nip_act', 'trilab_pl_partners_sync.check_gus_act']


# noinspection PyUnusedLocal
def migrate(cr, version):
    with cr.savepoint():
        for action in REMOVE_ACTIONS:
            _logger.info(f'remove action {action}')
            cr.execute(
                """
            SELECT id, res_id FROM ir_model_data
             WHERE model = 'ir.actions.act_window' AND module = %s AND name = %s""",
                action.split('.'),
            )

            for rec in cr.dictfetchall():
                cr.execute('DELETE FROM ir_act_window WHERE id = %s', (rec['res_id'],))
                cr.execute('DELETE FROM ir_model_data WHERE id = %s', (rec['id'],))

    _logger.info('migration pre 3.4 finished')
