# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from ..shopify.exceptions import ShopifyApiError


class SaleOrderCancel(models.TransientModel):
    _inherit = 'sale.order.cancel'

    refund_method = fields.Selection(
        selection=[
            ('original', 'Original payment method'),
            ('later', 'Later (refund in Shopify yourself)'),
        ],
        string='Refund Payments',
        default='original',
        required=True,
        help='How Shopify should handle the refund when cancelling this order:\n'
             '• Original payment method — refund the customer to their original payment.\n'
             '• Later — cancel without refunding now; issue the refund in Shopify when ready.\n'
             'Either way the refund is recorded in Shopify only — handle the Odoo-side refund '
             '(credit note / payment) separately.',
    )

    has_ecommerce_returns = fields.Boolean(
        string='Has E-Commerce Returns',
        compute='_compute_has_ecommerce_returns',
        help='Technical flag: the order has Shopify return(s) that may block cancellation.',
    )

    @api.depends('order_id')
    def _compute_has_ecommerce_returns(self):
        for wizard in self:
            wizard.has_ecommerce_returns = bool(
                wizard.order_id.external_return_ids.filtered(
                    lambda r: r.state not in ('canceled', 'declined')
                )
            )

    do_restock = fields.Boolean(
        string='Restock Inventory',
        default=True,
        help='Whether to restock the inventory committed to the order',
    )

    do_notify_customer = fields.Boolean(
        string='Send a Notification to the Customer',
        default=True,
    )

    reason_type = fields.Selection(
        selection=[
            ('CUSTOMER', 'Customer changed or canceled order'),
            ('DECLINED', 'Payment declined'),
            ('FRAUD', 'Fraudulent order'),
            ('INVENTORY', 'Items unavailable'),
            ('STAFF', 'Staff error'),
            ('OTHER', 'Other'),
        ],
        string='Reason for Cancellation',
        default='CUSTOMER',
        help='The reason for canceling the order',
    )

    staff_note = fields.Char(
        string='Staff Note',
        help='A staff-facing note about the order cancellation. This is not visible to the customer',
    )

    sub_state_external_ids = fields.Many2many(
        comodel_name='integration.sale.order.sub.status.external',
        relation='cancel_order_external_sub_state_relation',
        column1='wizard_id',
        column2='sub_state_external_id',
        string='E-Commerce Store Order Status(es)',
    )

    do_cancel_order_fulfillments = fields.Boolean(
        string='Cancel E-Commerce Fulfillments',
        help='Cancel the order\'s active Shopify fulfillment(s) before cancelling the order. '
             'Shopify can refuse to cancel an order that still has an outstanding fulfillment '
             '(for example one handled by a fulfillment service), so turn this on when the '
             'cancellation is blocked by a fulfillment, or when you want to explicitly cancel '
             'the shipment in Shopify. Leave it off for a normal cancel — Shopify usually '
             'handles fulfilled orders on its own (restocking per the Restock Inventory option).',
    )

    @property
    def ecommerce_active_fulfillments(self):
        return self.order_id.external_fulfillment_ids.filtered(lambda x: x.state == 'success')

    def action_open_integration_order(self):
        return self.order_id.action_open_order_in_external_system()

    def _check_integration_order_status(self):
        if not self.integration_id.is_integration_shopify:
            return super()._check_integration_order_status()

        # Order already removed from Shopify — nothing left to cancel there.
        external_id = self.order_id.external_order_name
        if external_id:
            remote_order = self.integration_id.adapter.gql.Order.set(id=external_id)
            remote_order.read(body='id')
            if not remote_order:
                return self.with_context(
                    cancel_integration_order_done=True,
                    cancel_integration_fulfillment_done=True,
                )

        # 1.Get actual fulfillments
        self.order_id\
            .with_context(skip_external_entity_dispatch=True) \
            .action_refresh_data_from_external(
                data={
                    'order_risks': [],
                    'payment_transactions': [],
                },
            )

        ctx = {
            'cancel_integration_fulfillment_done': not bool(self.ecommerce_active_fulfillments),
        }

        # 2. Get actual sub-statuses
        input_file = self.integration_input_file
        if not input_file:
            return self.with_context(**ctx)

        input_file.mark_for_update()
        order_data = input_file.update_current_pipeline()

        if not order_data:
            ctx.update(
                cancel_integration_order_done=True,
                cancel_integration_fulfillment_done=True,
            )
            return self.with_context(**ctx)

        sub_statuses = self.order_id.integration_pipeline.sub_state_external_ids

        if order_data.get('is_cancelled'):
            sub_statuses |= self.sub_state_external_ids.search([
                ('code', '=', 'cancelled'),
                ('integration_id', '=', self.integration_id.id),
            ])
            ctx.update(
                cancel_integration_order_done=True,
                cancel_integration_fulfillment_done=True,
            )

        self.sub_state_external_ids = [(6, 0, sub_statuses.ids)]
        return self.with_context(**ctx)

    def _get_refund_method(self):
        """Build Shopify's OrderCancelRefundMethodInput from the wizard selection.

        'original' refunds the customer to their original payment method; 'later' issues no
        refund now (the merchant refunds in Shopify when ready), expressed by omitting
        refundMethod entirely.
        """
        if self.refund_method == 'original':
            return {'originalPaymentMethodsRefund': True}
        return None

    def _format_cancel_error(self, error):
        """Turn a raw Shopify cancel error into a clear, actionable message."""
        message = str(error)
        lowered = message.lower()
        order_ref = self.order_id.external_sales_order_ref or self.order_id.name
        if 'has returns' in lowered:
            return _(
                "Shopify can't cancel order %(order)s because it has returns — Shopify does not "
                'allow cancelling an order that has returns. This step only mirrors the '
                'cancellation to Shopify; your Odoo order is already cancelled, so click Skip to '
                'finish.\n\n'
                'If a return is still open in Shopify, you can cancel or decline it there and '
                'retry. Completed (closed) returns cannot be removed, so an order with completed '
                'returns can only be cancelled in Odoo.'
            ) % {'order': order_ref}
        if 'fulfillment' in lowered and not self.do_cancel_order_fulfillments:
            return _(
                "Shopify can't cancel order %(order)s because it still has an active fulfillment. "
                'Turn on "Cancel E-Commerce Fulfillments" above and try again — that cancels the '
                'Shopify fulfillment(s) first so the order can be cancelled. Your Odoo order is '
                'already cancelled, so you can also click Skip to finish without cancelling it in '
                'Shopify.'
            ) % {'order': order_ref}
        return _(
            "Shopify couldn't cancel order %(order)s: %(message)s"
        ) % {'order': order_ref, 'message': message}

    def _action_cancel_integration(self):
        if not self.integration_id.is_integration_shopify:
            return super()._action_cancel_integration()

        # 1. Check input file
        input_file = self.integration_input_file
        if not input_file:
            return True, 'Cannot cancel in Shopify: external record is missing.'

        # 2. Cancel order fulfillments
        if self.do_cancel_order_fulfillments:
            for rec in self.ecommerce_active_fulfillments:
                rec.cancel_in_ecommerce_system()

        # 3. Cancel Shopify order
        if not self.env.context.get('cancel_integration_order_done'):
            params = {
                'reason': self.reason_type,
                'staff_note': self.staff_note or '',
                'restock': self.do_restock,
                'notify_customer': self.do_notify_customer,
                'refund_method': self._get_refund_method(),
            }
            try:
                input_file.cancel_order_in_ecommerce_system(params)
            except ShopifyApiError as ex:
                # Shopify refuses to cancel orders with active returns (and a few other states).
                # Surface a clear, actionable message instead of a raw API traceback.
                return False, self._format_cancel_error(ex)

        return True, ''
