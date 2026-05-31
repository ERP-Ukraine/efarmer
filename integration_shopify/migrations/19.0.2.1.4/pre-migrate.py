# See LICENSE file for full copyright and licensing details.

from odoo.addons.integration_shopify.shopify.resources import normalize_shopify_tracking_company


def migrate(cr, version):
    """
    Convert legacy Char values of delivery.carrier.shopify_code to Selection keys.

    Unknown values are mapped to ``other`` before the field type is changed on upgrade.
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'delivery_carrier'
          AND column_name = 'shopify_code'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT id, shopify_code
        FROM delivery_carrier
        WHERE shopify_code IS NOT NULL
          AND shopify_code != ''
    """)

    for carrier_id, shopify_code in cr.fetchall():
        shopify_code = normalize_shopify_tracking_company(shopify_code)

        if shopify_code:
            cr.execute(
                'UPDATE delivery_carrier SET shopify_code = %s WHERE id = %s',
                (shopify_code, carrier_id),
            )
