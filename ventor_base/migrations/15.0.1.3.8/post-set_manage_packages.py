from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})
    group_stock_tracking_lot = (
            env["res.config.settings"]
            .default_get("group_stock_tracking_lot")
            .get("group_stock_tracking_lot")
    )
    stock_picking_type_ids = env['stock.picking.type'].with_context(active_test=False).search([])

    if not group_stock_tracking_lot:
        stock_picking_type_ids.manage_packages = False

    elif group_stock_tracking_lot and not any(stock_picking_type_ids.mapped("manage_packages")):
        stock_picking_type_ids.manage_packages = True


    users = env['res.users'].with_context(active_test=False).search([
            ('allowed_warehouse_ids', '=', False),
            ('share', '=', False)
            ])
    warehouses = env["stock.warehouse"].with_context(active_test=False).search([])
    for user in users:
        if not user.allowed_warehouse_ids:
            user.allowed_warehouse_ids = [(6, 0, warehouses.ids)]
