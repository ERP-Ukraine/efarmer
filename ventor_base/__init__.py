# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from . import models
from . import report
from odoo import api, SUPERUSER_ID

def _post_init_hook(env):
    """
    This hook updates Ventor Settings in Operation Types
    And adds to all users to Ventor - Administrator Role
    """

    users_model = env['res.users']

    values = [(4, user.id) for user in users_model.search([]) if user.has_group('base.group_user')]
    env.ref('ventor_base.ventor_role_admin').user_ids = values

    env.cr.execute(
        """
        UPDATE stock_picking_type
        SET
            change_destination_location = True,
            show_next_product = CASE code when 'incoming' THEN False ELSE True END
        """
    )

    users = users_model.with_context(active_test=False).search(
        [
            ('allowed_warehouse_ids', '=', False),
            ('share', '=', False)
        ]
    )
    warehouses = env['stock.warehouse'].with_context(active_test=False).search([])
    for user in users:
        user.allowed_warehouse_ids = [(6, 0, warehouses.ids)]

    group_settings = env['res.config.settings'].default_get(
        [
            'group_stock_tracking_lot',
            'group_stock_tracking_owner',
        ]
    )

    # Enable Ventor settings related on Packages
    if group_settings.get('group_stock_tracking_lot'):
        ventor_packages_settings = env['ventor.option.setting'].search(
            [
                ('technical_name', '=', 'manage_packages'),
            ]
        )
        ventor_packages_settings.value = env.ref('ventor_base.bool_true')

    # Enable Ventor settings related on Consignment
    if group_settings.get('group_stock_tracking_owner'):
        ventor_owner_settings = env['ventor.option.setting'].search(
            [
                ('technical_name', '=', 'manage_product_owner'),
            ]
        )
        ventor_owner_settings.value = env.ref('ventor_base.bool_true')

    # Enable Ventor settings related on Quality Control module
    is_qc_installed = env.user.is_module_installed('quality_control')
    if is_qc_installed:
        # BP, CP, WP menus
        ventor_quality_control_settings = env['ventor.option.setting'].search(
            [
                ('technical_name', '=', 'quality_check_per_product_line'),
            ]
        )
        ventor_quality_control_settings.value = env.ref('ventor_base.bool_true')
        # WO operation types:
        stock_picking_type_ids = env['stock.picking.type'].with_context(active_test=False).search([])
        stock_picking_type_ids.quality_check_per_product_line = True
