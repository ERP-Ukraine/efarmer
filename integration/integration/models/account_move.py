# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    integration_id = fields.Many2one(
        string='e-Commerce Integration',
        comodel_name='sale.integration',
        readonly=True,
    )

    external_payment_method_id = fields.Many2one(
        string='e-Commerce Payment method',
        comodel_name='sale.order.payment.method',
        domain='[("integration_id", "=", integration_id)]',
        ondelete='set null',
        copy=False,
    )

    def action_post(self):
        # Inside the action_post() method invokes action_invoice_paid() because of
        # invoice may be zero amounted. In this case it is automatically marked as paid
        res = super(AccountMove, self).action_post()
        self.filtered(lambda x: x.is_invoice())._run_integration_validate_invoice_hooks()
        return res

    def action_invoice_paid(self):
        res = super(AccountMove, self).action_invoice_paid()
        self.filtered(lambda x: x.is_invoice())._run_integration_invoice_paid_hooks()
        return res

    def _run_integration_invoice_paid_hooks(self):
        total_result = list()

        for invoice in self:
            invoice_result = list()

            if invoice.payment_state in ('paid', 'in_payment'):
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    res = order._integration_paid_order_hook()
                    invoice_result.append((order, res))

            total_result.append((invoice, invoice_result))

        return total_result

    def _run_integration_validate_invoice_hooks(self):
        total_result = list()

        for invoice in self:
            invoice_result = list()

            if invoice.payment_state == 'not_paid':
                for order in invoice.invoice_line_ids.mapped('sale_line_ids.order_id'):
                    res = order._integration_validate_invoice_order_hook()
                    invoice_result.append((order, res))

            total_result.append((invoice, invoice_result))

        return total_result
