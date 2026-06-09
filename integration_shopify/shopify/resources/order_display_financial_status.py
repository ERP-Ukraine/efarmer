# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


FINANCIAL_STATUS_MAP = {
    'AUTHORIZED': (
        'Authorized',
        'The payment provider has validated the customer\'s payment information. '
        'This status appears only for manual payment capture and indicates payments should be captured before '
        'the authorization period expires.'
    ),
    'EXPIRED': (
        'Expired',
        'Payment wasn\'t captured before the payment provider\'s deadline on an '
        'authorized order. Some payment providers use this status to indicate failed payment processing.'
    ),
    'PAID': (
        'Paid',
        'Payment was automatically or manually captured, or the order was marked as paid.'
    ),
    'PARTIALLY_PAID': (
        'Partially Paid',
        'A payment was manually captured for the order with an amount less than the full order value.'
    ),
    'PARTIALLY_REFUNDED': (
        'Partially Refunded',
        'The amount refunded to a customer is less than the full amount paid for an order.'
    ),
    'PENDING': (
        'Pending',
        'Orders have this status when the payment provider needs time to complete the '
        'payment, or when manual payment methods are being used.'
    ),
    'REFUNDED': (
        'Refunded',
        'The full amount paid for an order was refunded to the customer.'
    ),
    'VOIDED': (
        'Voided',
        'An unpaid (payment authorized but not captured) order was manually canceled.'
    ),
}


class OrderDisplayFinancialStatus(StatusAbstract):

    authorized = 'AUTHORIZED'
    expired = 'EXPIRED'
    paid = 'PAID'
    partially_paid = 'PARTIALLY_PAID'
    partially_refunded = 'PARTIALLY_REFUNDED'
    pending = 'PENDING'
    refunded = 'REFUNDED'
    voided = 'VOIDED'

    @property
    def is_authorized(self):
        return self == self.authorized

    @property
    def is_expired(self):
        return self == self.expired

    @property
    def is_paid(self):
        return self == self.paid

    @property
    def is_partially_paid(self):
        return self == self.partially_paid

    @property
    def is_partially_refunded(self):
        return self == self.partially_refunded

    @property
    def is_pending(self):
        return self == self.pending

    @property
    def is_refunded(self):
        return self == self.refunded

    @property
    def is_voided(self):
        return self == self.voided

    @property
    def mapping(self):
        return FINANCIAL_STATUS_MAP
