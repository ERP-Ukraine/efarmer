# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


PAYOUT_TRANSACTION_TYPE_MAP = {
    'DEPOSIT': ('Deposit', 'Money deposited to the merchant bank account.'),
    'WITHDRAWAL': ('Withdrawal', 'Money withdrawn from the merchant bank account.'),
}


class ShopifyPaymentsPayoutTransactionType(StatusAbstract):
    """ShopifyPaymentsPayoutTransactionType — deposit or withdrawal."""

    deposit = 'DEPOSIT'
    withdrawal = 'WITHDRAWAL'

    @property
    def mapping(self):
        return PAYOUT_TRANSACTION_TYPE_MAP
