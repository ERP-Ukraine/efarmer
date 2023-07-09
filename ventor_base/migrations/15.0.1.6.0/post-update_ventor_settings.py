from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})

    lot_for_location_setting = env.ref("ventor_base.lot_for_location_int_transfers")
    lot_for_location_setting.write(
        {
            "description": "If it is active, you can select only lots from source location"
        }
    )
