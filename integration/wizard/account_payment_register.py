# See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        payments = super()._create_payments()

        if self.env.context.get('skip_dispatch_to_external'):
            return payments

        # Payments that have a move_id field are most likely already sent to integration via _invoice_paid_hook()

        payments_ = payments.filtered(
            lambda x: not x.move_id and x.payment_type == 'inbound' and x.partner_type == 'customer'
        )

        for payment in payments_:
            payment.invoice_ids.filtered(lambda x: x.is_invoice())._run_integration_invoice_paid_hooks()

        return payments
