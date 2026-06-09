# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


TRANSACTION_STATUS_MAP = {
    'AWAITING_RESPONSE': ('Awaiting a response.', 'Awaiting a response.'),
    'ERROR': ('Error', 'There was an error while processing the transaction.'),
    'FAILURE': ('Failure', 'The transaction failed.'),
    'PENDING': ('Pending', 'The transaction is pending.'),
    'SUCCESS': ('Success', 'The transaction succeeded.'),
}


class OrderTransactionStatus(StatusAbstract):

    awaiting_response = 'AWAITING_RESPONSE'
    error = 'ERROR'
    failure = 'FAILURE'
    pending = 'PENDING'
    success = 'SUCCESS'
    unknown = 'UNKNOWN'

    @property
    def is_awaiting_response(self):
        return self == self.awaiting_response

    @property
    def is_error(self):
        return self == self.error

    @property
    def is_failure(self):
        return self == self.failure

    @property
    def is_pending(self):
        return self == self.pending

    @property
    def is_success(self):
        return self == self.success

    @property
    def is_unknown(self):
        return self == self.unknown

    @property
    def mapping(self):
        return TRANSACTION_STATUS_MAP
