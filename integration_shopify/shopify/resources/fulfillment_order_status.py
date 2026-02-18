# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


FULFILLMENT_ORDER_STATUS_MAP = {
    'CANCELLED': ('Cancelled', 'The fulfillment was canceled.'),
    'CLOSED': ('Closed', 'The fulfillment has been completed and closed.'),
    'INCOMPLETE': ('Incomplete', 'The fulfillment cannot be completed as requested.'),
    'IN_PROGRESS': ('In Progress', 'The fulfillment is being processed.'),
    'ON_HOLD': ('On Hold', 'The fulfillment order is on hold.'),
    'OPEN': ('Open', 'The fulfillment order is ready for fulfillment.'),
    'SCHEDULED': (
        'Scheduled',
        'The fulfillment order is deferred and will be ready for fulfillment after the date '
        'and time specified in fulfill_at.',
    ),
}


class FulfillmentOrderStatus(StatusAbstract):

    cancelled = 'CANCELLED'
    closed = 'CLOSED'
    incomplete = 'INCOMPLETE'
    in_progress = 'IN_PROGRESS'
    on_hold = 'ON_HOLD'
    open = 'OPEN'
    scheduled = 'SCHEDULED'

    @property
    def is_cancelled(self):
        return self == self.cancelled

    @property
    def is_closed(self):
        return self == self.closed

    @property
    def is_incomplete(self):
        return self == self.incomplete

    @property
    def is_in_progress(self):
        return self == self.in_progress

    @property
    def is_on_hold(self):
        return self == self.on_hold

    @property
    def is_open(self):
        return self == self.open

    @property
    def is_scheduled(self):
        return self == self.scheduled

    @property
    def open_or_in_progress(self):
        return self in (self.open, self.in_progress)

    @property
    def mapping(self):
        return FULFILLMENT_ORDER_STATUS_MAP
