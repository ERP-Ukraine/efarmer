# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.cr.execute(
        """
        ALTER TABLE product_ecommerce_field_mapping
            ADD COLUMN IF NOT EXISTS import_enabled BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS export_enabled BOOLEAN DEFAULT FALSE;
        """
    )

    env.cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'product_ecommerce_field_mapping'
          AND column_name IN ('send_on_update', 'receive_on_import');
        """
    )

    existing_columns = {row[0] for row in env.cr.fetchall()}

    if {'send_on_update', 'receive_on_import'}.issubset(existing_columns):
        env.cr.execute(
            """
            UPDATE product_ecommerce_field_mapping
                SET
                    export_enabled = send_on_update,
                    import_enabled = receive_on_import;
            """
        )

    # In 1.19.x the is_default field on product.ecommerce.field had default=True,
    # so every customer-created field record also carried is_default=True into the
    # upgrade.  In 2.x that flag marks a record as a read-only system field in the
    # UI.  We must reset it to False for any record that has no ir.model.data entry
    # (i.e. records not defined in module XML — those are customer-created fields).
    # This runs in pre-migration so that the subsequent end-migration call to
    # create_fields_mapping_for_integration() correctly excludes custom fields.
    env.cr.execute(
        """
        UPDATE product_ecommerce_field pef
           SET is_default = FALSE
         WHERE pef.is_default = TRUE
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data imd
                WHERE imd.model = 'product.ecommerce.field'
                  AND imd.res_id = pef.id
           )
        """
    )
