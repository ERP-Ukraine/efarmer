# See LICENSE file for full copyright and licensing details.

from .. import STORAGE
from ....shopify.resources.order import Order as Order_


class Order(Order_):

    def get_by_pk(self, pk: int, body: str = None, **kw):
        return self.set(**STORAGE['order'][pk])
