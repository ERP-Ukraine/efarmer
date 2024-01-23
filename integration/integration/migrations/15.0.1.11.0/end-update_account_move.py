# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute(
        """
            UPDATE account_move am
            SET integration_id = so.integration_id,
                external_payment_method_id = so.payment_method_id
            FROM sale_order so
            JOIN sale_order_line sol ON sol.order_id = so.id
            JOIN sale_order_line_invoice_rel solir ON solir.order_line_id = sol.id
            JOIN account_move_line aml ON aml.id = solir.invoice_line_id
            WHERE am.move_type IN ('out_invoice','out_refund')
                AND am.id = aml.move_id
                AND so.integration_id IS NOT NULL;
        """
    )
