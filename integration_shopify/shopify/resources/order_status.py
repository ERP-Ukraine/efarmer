# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


ORDER_STATUS_MAP = {
    'OPEN': ('Open', 'Receive open orders.'),
    'CLOSED': ('Closed', 'Receive closed orders.'),
    'CANCELLED': ('Cancelled', 'Receive cancelled orders.'),
    'NOT_CLOSED': ('Not Closed', 'Receive not closed orders.'),
}


class OrderStatus(StatusAbstract):

    open = 'OPEN'
    closed = 'CLOSED'
    cancelled = 'CANCELLED'

    not_closed = 'NOT_CLOSED'  # Only for orders requests

    @property
    def is_open(self):
        return self == self.open

    @property
    def is_closed(self):
        return self == self.closed

    @property
    def is_cancelled(self):
        return self == self.cancelled

    @property
    def mapping(self):
        return ORDER_STATUS_MAP
