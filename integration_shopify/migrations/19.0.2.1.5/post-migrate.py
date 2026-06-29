# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """
    `is_shopify_metafield` changed from a non-stored computed field (derived from the
    `metafields.` prefix on `technical_name`) to a stored, user-editable Boolean.

    Preserve the previous behaviour for existing records by flagging every Shopify
    field whose API name used the legacy `metafields.` prefix.
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'product_ecommerce_field'
          AND column_name = 'is_shopify_metafield'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE product_ecommerce_field
        SET is_shopify_metafield = TRUE
        WHERE type_api = 'shopify'
          AND technical_name LIKE 'metafields.%'
          AND is_shopify_metafield IS NOT TRUE
    """)
