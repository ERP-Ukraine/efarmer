from odoo import SUPERUSER_ID, _, api


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})

    allow_validate_less = env.ref("ventor_base.allow_validate_less")
    allow_validate_less.write(
        {
            "name": "Validate uncompleted orders",
            "description": "User will be able to validate the order even if not all items were found"
        }
    )

    value = {
        "name": "Confirm destination package",
        "description": "User has to scan a barcode of destination package. "
        "The dot next to the field gets yellow color means user has to confirm it"
    }

    scan_destination_package_batch_picking = env.ref(
        "ventor_base.scan_destination_package_batch_picking",
        False,
    )
    scan_destination_package_cluster_picking = env.ref(
        "ventor_base.scan_destination_package_cluster_picking",
        False,
    )

    if scan_destination_package_batch_picking:
        scan_destination_package_batch_picking.write(value)
    if scan_destination_package_cluster_picking:
        scan_destination_package_cluster_picking.write(value)
