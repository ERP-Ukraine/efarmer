# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class FulfillmentOrderLineItem(GqlDict):

    _gid_name = 'FulfillmentOrderLineItem'
    _body = GqlDict._tmpl.FULFILLMENT_ORDER_LINE_ITEM_BODY

    @property
    def sale_line_item(self):
        self.ensure_one()
        return self._env.LineItem.set(**(self['lineItem'] or {}))

    @property
    def total_quantity(self):
        self.ensure_one()
        return self.totalQuantity or 0

    @property
    def remaining_quantity(self):
        self.ensure_one()
        return self.remainingQuantity or 0
