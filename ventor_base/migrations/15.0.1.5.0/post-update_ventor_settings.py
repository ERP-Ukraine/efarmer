from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})

    group_settings = env['res.config.settings'].default_get(
        [
            'group_stock_tracking_lot',
        ]
    )

    if group_settings.get('group_stock_tracking_lot'):
        ventor_packages_settings = env['ventor.option.setting'].search(
            [
                ('technical_name', '=', 'manage_packages'),
            ]
        )
        ventor_packages_settings.value = env.ref('ventor_base.bool_true')

    if group_settings.get('group_stock_tracking_owner'):
        ventor_owner_settings = env['ventor.option.setting'].search(
            [
                ('technical_name', '=', 'manage_product_owner'),
            ]
        )
        ventor_owner_settings.value = env.ref('ventor_base.bool_true')

    ventor_roles_administrator = env.ref('ventor_base.ventor_role_admin')
    ventor_roles_administrator.write(
        {
            'implied_ids': [(4, env.ref('ventor_base.merp_manage_ventor_configuration_app').id)],
        }
    )

    users = env['res.users'].with_context(active_test=False).search([
        ('share', '=', False)
        ])

    for user in users:
        if not user.has_group('ventor_base.ventor_role_wh_manager') and user.has_group(
                'ventor_base.ventor_role_wh_worker'
        ):
            user.write(
                {
                    'groups_id': [(3, env.ref('ventor_base.merp_menu_allow_changing_settings').id)]
                }
            )
        if user.ventor_user_settings:
            user.write(
                {
                    'groups_id': [(4, env.ref('ventor_base.merp_menu_use_local_user_device_settings').id)]
                }
            )

    #Adding the new group Scrap Management to Warehouse manager
    ventor_roles_warehouse_manager = env.ref('ventor_base.ventor_role_wh_manager')
    ventor_roles_warehouse_manager.write(
        {
            'implied_ids': [(4, env.ref('ventor_base.merp_scrap_management').id)]
        }
    )

    #Adding the new group Cluster Picking Menu to Warehouse worker
    ventor_roles_warehouse_worker = env.ref('ventor_base.ventor_role_wh_worker')
    ventor_roles_warehouse_worker.write(
        {
            'implied_ids': [(4, env.ref('ventor_base.merp_cluster_picking_menu').id)]
        }
    )
