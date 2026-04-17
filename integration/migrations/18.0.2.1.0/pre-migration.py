# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """
    Rename column auto_create_mapping to mapping_active_by_default
    to preserve existing customer data during the field rename.
    """
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'product_ecommerce_field'
          AND column_name IN ('auto_create_mapping', 'mapping_active_by_default')
    """)
    existing_columns = {row[0] for row in cr.fetchall()}
    if 'auto_create_mapping' in existing_columns and 'mapping_active_by_default' not in existing_columns:
        cr.execute("""
            ALTER TABLE product_ecommerce_field
            RENAME COLUMN auto_create_mapping TO mapping_active_by_default
        """)
