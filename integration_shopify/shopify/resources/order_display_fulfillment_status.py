# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


ORDER_DISPLAY_FULFILLMENT_STATUS_MAP = {
    'FULFILLED': (
        'Fulfilled',
        'All the items in the order have been fulfilled.'
    ),
    'IN_PROGRESS': (
        'In Progress',
        'Some of the items in the order have been fulfilled, or a request for '
        'fulfillment has been sent to the fulfillment service.'
    ),
    'ON_HOLD': (
        'On Hold',
        'All of the unfulfilled items in this order are on hold.'
    ),
    'PARTIALLY_FULFILLED': (
        'Partially Fulfilled',
        'Some of the items in the order have been fulfilled.'
    ),
    'REQUEST_DECLINED': (
        'Request Declined',
        'Some of the items in the order have been rejected for fulfillment by the fulfillment service.'
    ),
    'SCHEDULED': (
        'Scheduled',
        'All of the unfulfilled items in this order are scheduled for fulfillment at later time.'
    ),
    'UNFULFILLED': (
        'Unfulfilled',
        'None of the items in the order have been fulfilled.'
    ),

    # ----- Replaced
    'OPEN': (
        'Open',
        'None of the items in the order have been fulfilled. Replaced by "UNFULFILLED" status.'
    ),
    'PENDING_FULFILLMENT': (
        'Pending Fulfillment',
        'A request for fulfillment of some items awaits a response from '
        'the fulfillment service. Replaced by the "IN_PROGRESS" status.'
    ),
    'RESTOCKED': (
        'Restocked',
        'All the items in the order have been restocked. Replaced by the "UNFULFILLED" status.'
    ),
    # ----- Only for the orders requests
    'SHIPPED': (
        'Shipped',
        'Returns orders with fulfillment_status of fulfilled.'
    ),
    'UNSHIPPED': (
        'Unshipped',
        'Returns orders with fulfillment_status of null.'
    ),
    'PARTIAL': (
        'Partial',
        'Receive orders that have been partially shipped.'
    ),
}


class OrderDisplayFulfillmentStatus(StatusAbstract):

    fulfilled = 'FULFILLED'
    in_progress = 'IN_PROGRESS'
    on_hold = 'ON_HOLD'
    partially_fulfilled = 'PARTIALLY_FULFILLED'
    request_declined = 'REQUEST_DECLINED'
    scheduled = 'SCHEDULED'
    unfulfilled = 'UNFULFILLED'

    # ----- Replaced
    open = 'OPEN'
    pending_fulfillment = 'PENDING_FULFILLMENT'
    restocked = 'RESTOCKED'

    # ----- Only for the orders requests
    shipped = 'SHIPPED'
    unshipped = 'UNSHIPPED'
    partial = 'PARTIAL'

    @property
    def is_fulfilled(self):
        return self == self.fulfilled

    @property
    def is_in_progress(self):
        return self == self.in_progress

    @property
    def is_on_hold(self):
        return self == self.on_hold

    @property
    def is_partially_fulfilled(self):
        return self == self.partially_fulfilled

    @property
    def is_request_declined(self):
        return self == self.request_declined

    @property
    def is_scheduled(self):
        return self == self.scheduled

    @property
    def is_unfulfilled(self):
        return self == self.unfulfilled

    @property
    def mapping(self):
        return ORDER_DISPLAY_FULFILLMENT_STATUS_MAP
