# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SaleOrderCancel(models.TransientModel):
    _inherit = 'sale.order.cancel'

    do_refund = fields.Boolean(
        string='Refund',
        default=True,
        help='Whether to refund the amount paid by the customer',
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
            ('CUSTOMER', 'The customer wanted to cancel the order'),
            ('DECLINED', 'Payment was declined'),
            ('FRAUD', 'The order was fraudulent'),
            ('INVENTORY', 'There was insufficient inventory'),
            ('OTHER', 'The order was canceled for an unlisted reason'),
            ('STAFF', 'Staff made an error'),
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
    )

    @property
    def ecommerce_active_fulfillments(self):
        return self.order_id.external_fulfillment_ids.filtered(lambda x: x.external_status == 'success')

    def action_open_integration_order(self):
        return self.order_id.action_open_store_order()

    def _check_integration_order_status(self):
        if not self.integration_id.is_integration_shopify:
            return super()._check_integration_order_status()

        # 1.Get actual fulfillments
        self.order_id\
            .with_context(skip_integration_order_post_action=True) \
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
        order_data, __ = input_file.update_current_pipeline()

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
                'refund': ('false', 'true')[self.do_refund],
                'restock': ('false', 'true')[self.do_restock],
                'notify_cutomer': ('false', 'true')[self.do_notify_customer],
            }
            input_file.cancel_order_in_ecommerce_system(params)

        return True, ''
