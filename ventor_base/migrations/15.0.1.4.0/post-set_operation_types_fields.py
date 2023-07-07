from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})
    stock_picking_type_ids = env['stock.picking.type'].with_context(active_test=False).search([])
    
    group_stock_production_lot = (
            env["res.config.settings"]
            .default_get("group_stock_production_lot")
            .get("group_stock_production_lot")
    )

    if not group_stock_production_lot:
        stock_picking_type_ids.apply_default_lots = False

    group_stock_tracking_owner = (
            env["res.config.settings"]
            .default_get("group_stock_tracking_owner")
            .get("group_stock_tracking_owner")
    )

    if not group_stock_tracking_owner:
        stock_picking_type_ids.manage_product_owner = False

    elif group_stock_tracking_owner and not any(stock_picking_type_ids.mapped("manage_product_owner")):
        stock_picking_type_ids.manage_product_owner = True
