# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


PAYOUT_STATUS_MAP = {
    'SCHEDULED': ('Scheduled', 'Payout is scheduled but money has not moved yet.'),
    'PAID': ('Paid', 'Payout has been paid.'),
    'FAILED': ('Failed', 'Payout failed.'),
    'CANCELED': ('Canceled', 'Payout was canceled.'),
}


class ShopifyPaymentsPayoutStatus(StatusAbstract):
    """Known ShopifyPaymentsPayoutStatus values.

    Stored as Char in Odoo because live data can return undocumented values
    (e.g. IN_TRANSIT on associatedPayout.status). The enum covers the introspected set.
    """

    scheduled = 'SCHEDULED'
    paid = 'PAID'
    failed = 'FAILED'
    canceled = 'CANCELED'

    @property
    def mapping(self):
        return PAYOUT_STATUS_MAP

    @property
    def is_terminal(self):
        return self in (self.paid, self.failed, self.canceled)
