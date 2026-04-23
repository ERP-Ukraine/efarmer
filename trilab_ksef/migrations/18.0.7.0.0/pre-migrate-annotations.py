import logging

from odoo import api, SUPERUSER_ID
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(f'Start migration from {version} - pre migrate annotations')

    update_xml = False

    if column_exists(cr, 'account_move', 'x_ksef_p_18'):
        cr.execute("""
            UPDATE account_move SET x_pl_vat_reverse_charge = TRUE
             WHERE x_ksef_p_18 = TRUE AND x_pl_vat_reverse_charge = FALSE
        """)
        update_xml = True

    if column_exists(cr, 'account_move', 'x_ksef_p_18a'):
        cr.execute("""
            UPDATE account_move SET x_pl_vat_mpp = TRUE
             WHERE x_ksef_p_18a = TRUE AND x_pl_vat_mpp = FALSE
        """)
        update_xml = True

    if column_exists(cr, 'account_move', 'x_ksef_p_23'):
        cr.execute("""
            UPDATE account_move SET x_pl_vat_tt_d = TRUE
             WHERE x_ksef_p_23 = TRUE AND move_type IN ('out_invoice', 'out_refund')
               AND x_pl_vat_tt_d = FALSE
        """)
        cr.execute("""
            UPDATE account_move SET x_pl_vat_tt_wnt = TRUE
             WHERE x_ksef_p_23 = TRUE AND move_type IN ('in_invoice', 'in_refund')
               AND x_pl_vat_tt_wnt = FALSE
        """)
        update_xml = True

    if update_xml:
        env = api.Environment(cr, SUPERUSER_ID, {})
        if view_id := env.ref('trilab_ksef.view_move_form_ti_inherit', raise_if_not_found=False):
            _logger.info('remove trilab_ksef.view_move_form_ti_inherit view')
            view_id.unlink()

        if view_id := env.ref('trilab_ksef.view_move_form_inherit', raise_if_not_found=False):
            _logger.info('remove trilab_ksef.view_move_form_inherit view')
            view_id.unlink()

    _logger.info(f'Finished migration from {version} - pre migrate annotations')
