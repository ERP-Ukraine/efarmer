from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})

    ventor_roles_warehouse_worker = env.ref('ventor_base.ventor_role_wh_worker')
    ventor_roles_warehouse_worker.write(
        {
            'implied_ids': [
                (4, env.ref('ventor_base.merp_wave_picking_menu').id),
            ]
        }
    )
