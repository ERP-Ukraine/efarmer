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
        UPDATE product_ecommerce_field_mapping
            SET
                export_enabled = send_on_update,
                import_enabled = receive_on_import;
        """
    )
