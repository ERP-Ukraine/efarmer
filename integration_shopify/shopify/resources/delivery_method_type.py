# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


DELIVERY_METHOD_TYPE_MAP = {
    'LOCAL': ('Local', 'The order is delivered using a local delivery service.'),
    'NONE': ('None', 'Non-physical items, no delivery needed.'),
    'PICK_UP': ('Pick Up', 'The order is picked up by the customer.'),
    'PICKUP_POINT': ('Pickup Point', 'The order is delivered to a pickup point.'),
    'RETAIL': ('Retail', 'In-store sale, no delivery needed.'),
    'SHIPPING': ('Shipping', 'The order is shipped.'),
}


class DeliveryMethodType(StatusAbstract):

    local = 'LOCAL'
    none = 'NONE'
    pick_up = 'PICK_UP'
    pickup_point = 'PICKUP_POINT'
    retail = 'RETAIL'
    shipping = 'SHIPPING'

    @property
    def is_local(self):
        return self == self.local

    @property
    def is_none(self):
        return self == self.none

    @property
    def is_pick_up(self):
        return self == self.pick_up

    @property
    def is_pickup_point(self):
        return self == self.pickup_point

    @property
    def is_retail(self):
        return self == self.retail

    @property
    def is_shipping(self):
        return self == self.shipping

    @property
    def mapping(self):
        return DELIVERY_METHOD_TYPE_MAP
