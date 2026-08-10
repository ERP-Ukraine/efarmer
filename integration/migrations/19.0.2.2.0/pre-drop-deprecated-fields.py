# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


LEGACY_PRICELIST_ACTION_XMLIDS = (
    'integration.product_pricelist_action_force_export_to_external',
    'integration.product_pricelist_action_update_to_external',
)


def migrate(cr, version):
    _migrate_apply_to_products(cr)
    _remove_legacy_pricelist_actions(cr)


def _migrate_apply_to_products(cr):
    """Carry the old "apply_to_products" setting forward into the new "auto_export_new_products".

    The old `apply_to_products` field was removed in 2.1.7; its column may still exist as an orphan on databases
    upgrading from an earlier version. Where it does, copy the value into the new field and drop the orphan column.
    On databases where the column is already gone this is a no-op.
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'sale_integration'
          AND column_name = 'apply_to_products'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE sale_integration
        SET auto_export_new_products = apply_to_products
        WHERE apply_to_products IS TRUE
    """)
    cr.execute("ALTER TABLE sale_integration DROP COLUMN apply_to_products")


def _remove_legacy_pricelist_actions(cr):
    """Remove generic pricelist actions moved to connector modules."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    for xmlid in LEGACY_PRICELIST_ACTION_XMLIDS:
        action = env.ref(xmlid, raise_if_not_found=False)
        if action:
            action.unlink()
