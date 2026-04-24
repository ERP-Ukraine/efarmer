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
        res = super(AccountMove, self)._invoice_paid_hook()

        self.filtered(lambda x: x.is_invoice())._run_integration_invoice_paid_hooks()

        return res

    def _run_integration_invoice_paid_hooks(self):
        total_result = list()

        for invoice in self:
            invoice_result = list()

            if invoice.invoice_is_paid:
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    res = order._integration_paid_order_hook()
                    invoice_result.append((order, res))

            total_result.append((invoice, invoice_result))

        return total_result

    def _integration_post_invoice_post(self):
        for invoice in self:
            if not invoice.is_invoice():
                continue

            # This hook mark order as paid in e-commerce system (if payment method configured that way)
            if invoice.invoice_not_paid:
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    order._integration_validate_invoice_order_hook()

            # Apply external payments
            for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                order._integration_apply_external_payments()
