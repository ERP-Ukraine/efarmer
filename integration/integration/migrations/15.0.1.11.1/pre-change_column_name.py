# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'account_move' AND column_name = 'payment_method_id';
        """
    )
    result = cr.fetchone()
    if result is not None:
        cr.execute(
            """
                ALTER TABLE account_move
                RENAME COLUMN payment_method_id
                TO external_payment_method_id
            """
        )
