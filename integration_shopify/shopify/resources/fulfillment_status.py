# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


FULFILLMENT_STATUS_MAP = {
    'CANCELLED': ('Cancelled', 'The fulfillment was canceled.'),
    'ERROR': ('Error', 'There was an error with the fulfillment request.'),
    'FAILURE': ('Failure', 'The fulfillment request failed.'),
    'SUCCESS': ('Success', 'The fulfillment was completed successfully.'),
}


class FulfillmentStatus(StatusAbstract):

    cancelled = 'CANCELLED'
    error = 'ERROR'
    failure = 'FAILURE'
    success = 'SUCCESS'

    @property
    def is_cancelled(self):
        return self == self.cancelled

    @property
    def is_error(self):
        return self == self.error

    @property
    def is_failure(self):
        return self == self.failure

    @property
    def is_success(self):
        return self == self.success

    @property
    def mapping(self):
        return FULFILLMENT_STATUS_MAP
