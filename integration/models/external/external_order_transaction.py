# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields, _

from ...exceptions import ErrorStore as es


_logger = logging.getLogger(__name__)


REFUND_FOUND_ERROR = """\n\n
⚠️  REFUND TRANSACTION DETECTED ⚠️

This order contains a refund transaction that cannot be processed automatically.

To resolve this issue, please choose one of the following options:

OPTION 1: Adjust Auto-Workflow Settings
    • Go to E-Commerce Integrations → Stores → [Your Store] → Sales Orders tab
    • Uncheck "Auto-Apply Payments from E-Commerce System"
    • Re-run the integration job to validate invoices and register payments automatically
    • The system will ignore e-commerce transaction details and use validated invoice data instead

OPTION 2: Manual Transaction Processing
    • Open the sales order in Odoo
    • Review transaction details in the E-Commerce Integration tab
    • Process payments and refunds manually in the associated invoice
    • Mark auto-workflow steps as completed using the "Integration Workflow" button

For assistance, contact your system administrator or refer to the integration documentation.
"""


class ExternalOrderTransaction(models.Model):
    _name = 'external.order.transaction'
    _inherit = 'external.order.resource'
    _description = 'External Order Payment Transaction'

    transaction = fields.Char(
        string='Transaction ID',
        help='Unique identifier for this payment transaction',
    )
    kind = fields.Selection(
        selection=[
            ('authorization', 'Payment Authorization'),
            ('capture', 'Payment Capture'),
            ('sale', 'Direct Sale'),
            ('void', 'Transaction Void'),
            ('refund', 'Payment Refund'),
            ('other', 'Other Transaction'),
        ],
        string='Transaction Type',
        default='other',
        help="""
            Payment Authorization: Customer approval to charge their payment method
                (valid for 7-30 days depending on your payment processor)

            Payment Capture: Transfer of previously authorized funds to your account

            Direct Sale: Immediate authorization and capture in a single transaction

            Transaction Void: Cancellation of a pending authorization or capture

            Payment Refund: Return of captured funds to the customer

            Other Transaction: Any other transaction type not listed above
        """,
    )
    amount = fields.Char(
        string='Transaction Amount',
        help='Payment amount in the original currency',
    )
    currency = fields.Char(
        string='Currency Code',
        help='ISO currency code (e.g., USD, EUR, GBP)',
    )
    gateway = fields.Char(
        string='Payment Gateway',
        help='Payment processor or gateway used (e.g., Stripe, PayPal, Square)',
    )
    external_parent_str_id = fields.Char(
        string='Parent Transaction ID',
        help='Reference to the original transaction for refunds or captures',
    )
    payment_ids = fields.One2many(
        comodel_name='account.payment',
        inverse_name='integration_transaction_id',
        string='Odoo Payments',
        help='Associated payment records created in Odoo',
    )
    external_process_date = fields.Date(
        string='Transaction Date',
        default=fields.Date.today,
        help='Date when the transaction was processed in the external system',
    )

    @api.depends('erp_order_id.name', 'name')
    def _compute_display_name(self):
        """Generate a user-friendly display name for the transaction"""
        for rec in self:
            rec.display_name = f'{rec.erp_order_id.name}: {rec.name}'

    def _compute_is_ecommerce_ok(self):
        """Check if the transaction status allows processing in Odoo"""
        for rec in self:
            rec.is_ecommerce_ok = (rec.external_status == 'success')

    @property
    def float_amount(self):
        """Convert amount string to float for calculations"""
        return float(self.amount)

    @property
    def is_refund(self):
        """Check if this is a refund transaction"""
        return self.kind == 'refund'

    def validate(self):
        """
        Advance payment flow and fall back to standard validation
        """
        if (
            self.env.context.get('integration_skip_advance_payment')
            or not self.integration_id.create_advance_payments
        ):
            return super().validate()

        result, ids = self._validate_as_advance_payment()

        if not result:
            self._log_processing_failed()

        return result, ids

    def _validate(self):
        """
        Process the external payment transaction in Odoo.

        Creates payment records and reconciles them with unpaid invoices.

        Returns:
            tuple: (success, payment_ids)
        """
        self.internal_info = False

        if self.is_done:
            return True, []

        if not self.is_ecommerce_ok:
            self.internal_info = _('Transaction skipped - external status does not allow processing')
            self.mark_skipped()
            return False, []

        invoices = self.erp_order_id.actual_invoice_ids\
            .filtered(lambda x: x.invoice_is_posted and x.invoice_to_pay)

        if not invoices:
            self.internal_info = _('No unpaid invoices found for this order')
            self.mark_skipped()
            return False, []

        wizard = self.env['account.payment.register'] \
            .with_context(
                active_ids=invoices.ids,
                active_model=invoices._name,
                default_integration_id=self.integration_id.id,
            ).create({
                'amount': self.get_amount(),
                'journal_id': self.get_journal(),
                'payment_date': self.get_payment_date(),
                'payment_difference_handling': 'open',
            })

        if wizard.payment_difference < 0:
            wizard.payment_difference_handling = 'reconcile'
            wizard.writeoff_account_id = self.get_writeoff_account()

        try:
            payments = wizard._create_payments()
        except (es.UserError, es.ValidationError) as ex:
            self.internal_info = f'Payment creation failed: {ex.args[0]}'
            self.mark_failed()
            return False, []

        self._add_payment_ids(payments.ids)
        self.mark_done()

        return True, payments.ids

    def _validate_as_advance_payment(self):
        """
        Validate the external payment transaction as an advance payment
        using the sale_advance_payment OCA module wizard.

        Returns:
            tuple: (success, payment_ids)
        """
        self.internal_info = False

        if self.is_done:
            return True, []

        if not self.is_ecommerce_ok:
            self.internal_info = _('Transaction skipped - external status does not allow processing')
            self.mark_skipped()
            return False, []

        order = self.erp_order_id
        old_payments = order.account_payment_ids

        try:
            wizard = self.env['account.voucher.wizard'] \
                .with_context(
                    active_ids=order.ids,
                    default_integration_id=self.integration_id.id,
                ).create({
                    'order_id': order.id,
                    'amount_total': order.amount_residual,
                    'amount_advance': self.get_amount(no_writeoff=True),
                    'currency_id': order.pricelist_id.currency_id.id,
                    'journal_id': self.get_journal(),
                    'date': self.get_payment_date(),
                })

            wizard.make_advance_payment()
        except (es.UserError, es.ValidationError) as ex:
            self.internal_info = f'Advance payment creation failed: {ex.args[0]}'
            self.mark_failed()
            return False, []

        new_payments = order.account_payment_ids - old_payments
        self._add_payment_ids(new_payments.ids)
        self.mark_done()

        return True, new_payments.ids

    def get_journal(self):
        """Get the appropriate payment journal for this transaction"""
        if self.gateway:
            payment_method = self.env['sale.order.payment.method'].from_external(self.integration_id, self.gateway)
            payment_method_external = payment_method.to_external_record(self.integration_id)
            payment_method_external._raise_for_missing_journal()

            journal = payment_method_external.payment_journal_id
        else:
            journal = self.erp_order_id.integration_pipeline.get_payment_journal_or_raise()

        return journal.id

    def get_amount(self, no_writeoff: bool = False):
        """Convert external amount to Odoo invoice currency"""
        if not self.currency:
            raise es.ValidationError(_('Currency code is missing in the transaction data.'))
        external_currency = self.env['res.currency'].search([
            ('name', '=ilike', self.currency.lower()),
        ], limit=1)

        if not external_currency:
            raise es.ApiImportError(
                _('Currency "%s" is not configured in Odoo. Please add this currency to continue.') % self.currency
            )

        order = self.erp_order_id
        order_currency = order.pricelist_id.currency_id

        if order_currency.id != external_currency.id:
            amount = order_currency._convert(
                from_amount=self.float_amount,
                to_currency=order_currency,
                company=order.company_id,
                date=self.get_payment_date(),
            )
        else:
            amount = self.float_amount

        if no_writeoff:
            if amount < order.amount_residual:
                amount = order.amount_residual

        return amount

    def get_payment_date(self):
        """Prepare the payment date for the payment register wizard"""
        return self.external_process_date or fields.Date.context_today(self)

    def get_writeoff_account(self):
        """Get the write-off account for payment differences"""
        writeoff_account = self.integration_id.integration_writeoff_account_id

        if not writeoff_account:
            raise es.ValidationError(
                _(
                    'Integration "%s": Write-off account is not configured. '
                    'Please set up a write-off account in the integration settings.'
                ) % self.integration_name
            )

        return writeoff_account.id

    def _add_payment_ids(self, ids):
        """Link created payment records to this transaction"""
        self.payment_ids = [(4, id_, 0) for id_ in ids]

    def _raise_if_refund_found(self):
        """Check for unprocessed refund transactions and raise user-friendly error"""
        if any(x.is_refund for x in self if not x.is_done):
            raise es.ValidationError(REFUND_FOUND_ERROR)
