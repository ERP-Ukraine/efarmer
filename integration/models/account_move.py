# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        readonly=True,
    )

    external_payment_method_id = fields.Many2one(
        string='E-Commerce Payment Method',
        comodel_name='sale.order.payment.method',
        domain='[("integration_id", "=", integration_id)]',
        ondelete='set null',
        copy=False,
    )

    @property
    def invoice_is_posted(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.state == 'posted'

    @property
    def invoice_is_paid(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.payment_state in ('paid', 'in_payment')

    @property
    def invoice_not_paid(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.payment_state == 'not_paid'

    @property
    def invoice_to_pay(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.payment_state in ('not_paid', 'partial')

    def action_post(self):
        # Inside the action_post() method invokes _invoice_paid_hook() because of
        # invoice may be zero amounted. In this case it is automatically marked as paid
        res = super(AccountMove, self).action_post()

        self._integration_post_invoice_post()

        return res

    def _invoice_paid_hook(self):
        """Lifecycle hook: extends Odoo's account.move._invoice_paid_hook to fan
        out to the integration's invoice-paid hooks on the invoice's sale orders.
        """
        res = super(AccountMove, self)._invoice_paid_hook()

        self.filtered(lambda x: x.is_invoice())._run_integration_invoice_paid_hooks()

        return res

    def _run_integration_invoice_paid_hooks(self):
        """Lifecycle hook: invoice paid → enqueue entity processing.

        Refunds attempted on invoice post may have been deferred (the invoice wasn't paid yet,
        so credit-note auto-reconciliation would have eaten the invoice balance). Now that the
        invoice is paid, enqueue processing to retry all pending entities. The hook only
        triggers — all business logic lives in the processing job.
        """
        total_result = list()

        for invoice in self:
            invoice_result = list()

            if invoice.invoice_is_paid:
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    res = order._integration_paid_order_hook()
                    invoice_result.append((order, res))

                    order._enqueue_external_entities_processing()

            total_result.append((invoice, invoice_result))

        return total_result

    def _integration_post_invoice_post(self):
        """Lifecycle hook: invoice posted → enqueue entity processing.

        Enqueues a job that processes all pending entities (fulfillments, payments, returns,
        refunds) in dependency order. If the invoice is not yet paid, refunds will be deferred
        and retried on the paid hook above. The hook only triggers — all business logic lives
        in the processing job.
        """
        if self.env.context.get('skip_external_entity_dispatch'):
            return

        for invoice in self:
            if not invoice.is_invoice():
                continue

            if invoice.invoice_not_paid:
                # Notify the e-commerce platform about the validated invoice
                # (some payment methods mark the order as paid at this point).
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    order._integration_validate_invoice_order_hook()

            # Enqueue per-order processing for any external entities whose prerequisites the
            # just-posted invoice may have unlocked. The dispatcher's transaction stage
            # registers external payments against the freshly posted invoice, which is what
            # the direct _integration_apply_external_payments() call used to do here.
            for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                order._enqueue_external_entities_processing()
