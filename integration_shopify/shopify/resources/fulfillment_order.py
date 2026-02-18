# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate


class FulfillmentOrder(ShopifyResourceUpdate):

    _gid_name = 'FulfillmentOrder'
    _request_name = 'fulfillmentOrder'
    _body = ShopifyResourceUpdate._tmpl.FULFILLMENT_ORDER_BODY

    MUTATION_FULFILLMENT_ORDER_MOVE = ShopifyResourceUpdate._tmpl.MUTATION_FULFILLMENT_ORDER_MOVE
    MUTATION_FULFILLMENT_ORDER_SPLIT = ShopifyResourceUpdate._tmpl.MUTATION_FULFILLMENT_ORDER_SPLIT

    FULFILLMENT_ORDER_GET_DELIVERY_METHODS_BODY = ShopifyResourceUpdate._tmpl \
        .FULFILLMENT_ORDER_GET_DELIVERY_METHODS_BODY

    @property
    def status(self):
        self.ensure_one()
        return self._env.FulfillmentOrderStatus(self['status'])

    @property
    def is_closed(self):
        self.ensure_one()
        return self.status.is_closed

    @property
    def is_cancelled(self):
        self.ensure_one()
        return self.status.is_cancelled

    @property
    def line_items(self):
        self.ensure_one()
        return [self._env.FulfillmentOrderLineItem.set(**x) for x in (self['lineItems'] or [])]

    @property
    def delivery_method(self):
        self.ensure_one()
        return self._env.DeliveryMethod.set(**(self['deliveryMethod'] or {}))

    @property
    def location(self):
        self.ensure_one()
        data = (self['assignedLocation'] or {}).get('location') or {}
        return self._env.Location.set(**data)

    @property
    def closed_before_fulfill(self):
        self.ensure_one()
        return self.is_closed and all((x.total_quantity == x.remaining_quantity) for x in self.line_items)

    @property
    def fulfill_at(self):
        self.ensure_one()
        return self['fulfillAt']

    @property
    def fulfill_by(self):
        self.ensure_one()
        return self['fulfillBy']

    @property
    def updated_at(self):
        self.ensure_one()
        return self['updatedAt']

    @property
    def fulfillments(self):
        self.ensure_one()

        if not self.key_exist('fulfillments'):
            self.get_fulfillments()

        return [self._env.Fulfillment.set(**vals) for vals in (self['fulfillments'] or [])]

    def get_batch_for_delivery_methods(self):
        return self.get_batch(
            body=self.FULFILLMENT_ORDER_GET_DELIVERY_METHODS_BODY,
            arguments='includeClosed: true, sortKey: ID, reverse: true',
        )

    def get_fulfillments(self):
        self.ensure_one()

        body = 'id fulfillments(first: 25) { nodes { %s } }' % self._env.Fulfillment.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(fulfillments=result['fulfillments'])

        return self['fulfillments']

    def fulfill(
        self,
        *,
        carrier: str,
        tracking_numbers: list,
        url: str = None,
        lines_data: list = None,
        notify_customer: bool = True,
    ):
        self.ensure_one()

        fulfillment = self._env.Fulfillment.create(
            fulfillment_order_id=self.gid,
            carrier=carrier,
            tracking_numbers=tracking_numbers,
            url=url,
            lines_data=lines_data,
            notify_customer=notify_customer,
        )

        self.read()

        return fulfillment

    def auto_fulfill(self, notify_customer: bool = True):
        """
        Auto fulfill the fulfillment order by moving the lines
        to the fulfillments without any tracking information
        """
        self.ensure_one()

        return self.fulfill(
            carrier='',
            tracking_numbers='',
            url='',
            lines_data=self._prepare_fulfillment_lines_data(),
            notify_customer=notify_customer,
        )

    def split(self, lines_data: list):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_FULFILLMENT_ORDER_SPLIT,
            variables={
                'fulfillmentOrderSplits': [{
                    'fulfillmentOrderId': self.gid,
                    'fulfillmentOrderLineItems': lines_data,
                }],
            },
            user_errors_path='data.fulfillmentOrderSplit.userErrors',
        )

        result = self._extract(
            response,
            'data.fulfillmentOrderSplit.fulfillmentOrderSplits.0.remainingFulfillmentOrder',
            dict,
        )

        return self.new(**result)

    def move(self, location_id: int):
        self.ensure_one()

        location_gid = self._env.Location.create_gid(location_id)
        if location_gid == self.location.gid:
            return self

        response = self.execute(
            self.MUTATION_FULFILLMENT_ORDER_MOVE,
            variables={
                'id': self.gid,
                'newLocationId': location_gid,
            },
            user_errors_path='data.fulfillmentOrderMove.userErrors',
        )

        result = self._extract(response, 'data.fulfillmentOrderMove.movedFulfillmentOrder', dict)

        return self.set(**result)

    def _prepare_fulfillment_lines_data(self):
        lines = filter(lambda x: x.remaining_quantity, self.line_items)
        return [{'id': x.gid, 'quantity': x.remaining_quantity} for x in lines]

    def _prepare_fulfillment_single_line_data(self, sale_line_id: int, qty: int):
        line = self._get_fulfillment_line(sale_line_id)

        if not line:
            return dict()

        pending_qty = line.remaining_quantity

        if not pending_qty:
            return dict()

        if qty > pending_qty:
            qty = pending_qty

        return {
            'quantity': qty,
            'id': line.gid,
        }

    def _get_fulfillment_line(self, sale_line_id: int):
        f = filter(
            lambda x: x.remaining_quantity and x.sale_line_item.id == sale_line_id,
            self.line_items,
        )
        return next(f, False)
