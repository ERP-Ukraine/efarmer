# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


ORDER_RETURN_STATUS_MAP = {
    'IN_PROGRESS': 'Some items in the order are being returned',
    'INSPECTION_COMPLETE': 'All return shipments from a return in this order were inspected.',
    'NO_RETURN': 'No items in the order were returned.',
    'RETURN_FAILED': 'Some returns in the order were not completed successfully.',
    'RETURN_REQUESTED': 'A return was requested for some items in the order.',
    'RETURNED': 'Some items in the order were returned.',
}


class OrderReturnStatus(StatusAbstract):

    in_progress = 'IN_PROGRESS'
    inspection_complete = 'INSPECTION_COMPLETE'
    no_return = 'NO_RETURN'
    return_failed = 'RETURN_FAILED'
    return_requested = 'RETURN_REQUESTED'
    returned = 'RETURNED'

    @property
    def is_in_progress(self):
        return self == self.in_progress

    @property
    def is_inspection_complete(self):
        return self == self.inspection_complete

    @property
    def is_no_return(self):
        return self == self.no_return

    @property
    def is_return_failed(self):
        return self == self.return_failed

    @property
    def is_return_requested(self):
        return self == self.return_requested

    @property
    def is_returned(self):
        return self == self.returned

    @property
    def mapping(self):
        return ORDER_RETURN_STATUS_MAP
