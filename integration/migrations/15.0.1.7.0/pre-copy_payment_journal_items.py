# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.cr.execute(
        """
        ALTER TABLE integration_sale_order_payment_method_external
        ADD COLUMN payment_journal_id INT
        REFERENCES account_journal
        """
    )

    env.cr.execute(
        """
        UPDATE integration_sale_order_payment_method_external as x
        SET payment_journal_id = (
            SELECT payment_journal_id
            FROM integration_sale_order_payment_method_mapping
            WHERE external_payment_method_id = x.id
        )
        """
    )
