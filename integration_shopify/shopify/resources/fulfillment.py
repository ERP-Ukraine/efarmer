# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate


class Fulfillment(ShopifyResourceUpdate):

    _gid_name = 'Fulfillment'
    _request_name = 'fulfillment'
    _body = ShopifyResourceUpdate._tmpl.FULFILLMENT_BODY

    MUTATION_CREATE = ShopifyResourceUpdate._tmpl.MUTATION_FULFILLMENT_CREATE
    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_FULFILLMENT_UPDATE
    MUTATION_CANCEL = ShopifyResourceUpdate._tmpl.MUTATION_CANCEL_FULFILLMENT

    @property
    def order(self):
        self.ensure_one()
        return self._env.Order.set(**(self['order'] or {}))

    @property
    def location(self):
        self.ensure_one()
        return self._env.Location.set(**(self['location'] or {}))

    @property
    def status(self):
        self.ensure_one()
        return self._env.FulfillmentStatus(self['status'])

    @property
    def fulfillment_line_items(self):
        self.ensure_one()
        return [self._env.FulfillmentLineItem.set(**x) for x in (self['fulfillmentLineItems'] or [])]

    @property
    def tracking_info(self):
        self.ensure_one()
        return self['trackingInfo'] or []

    @property
    def tracking_numbers(self):
        self.ensure_one()
        return [x['number'] for x in self.tracking_info]

    @property
    def tracking_company(self):
        self.ensure_one()

        if not self.tracking_info:
            return ''

        return self.tracking_info[0]['company']

    @property
    def location_id(self):
        self.ensure_one()

        if not self.location:
            return ''

        return self.location['id']

    def create(
        self,
        *,
        fulfillment_order_id: str,
        carrier: str,
        tracking_numbers: list,
        url: str = None,
        lines_data: list = None,
        notify_customer: bool = True,
    ):
        self.ensure_new()

        response = self.execute(
            self.MUTATION_CREATE,
            variables={
                'fulfillment': {
                    'lineItemsByFulfillmentOrder': [{
                        'fulfillmentOrderId': self._env.FulfillmentOrder.create_gid(fulfillment_order_id),
                        'fulfillmentOrderLineItems': lines_data,
                    }],
                    'notifyCustomer': notify_customer,
                    'trackingInfo': {
                        'company': carrier,
                        'numbers': tracking_numbers,
                        'url': url,
                    },
                },
            },
            user_errors_path='data.fulfillmentCreate.userErrors',
        )

        result = self._extract(response, 'data.fulfillmentCreate.fulfillment', dict)

        return self.new(**result)

    def update(self, *, company: str, tracking_numbers: list, notify_customer: bool = True):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'fulfillmentId': self.gid,
                'notifyCustomer': notify_customer,
                'trackingInfoInput': {
                    'company': company,
                    'numbers': tracking_numbers,
                }
            },
            user_errors_path='data.fulfillmentTrackingInfoUpdate.userErrors',
        )

        result = self._extract(response, 'data.fulfillmentTrackingInfoUpdate.fulfillment', dict)

        return self.set(**result)

    def cancel(self):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_CANCEL,
            variables={
                'id': self.gid,
            },
            user_errors_path='data.fulfillmentCancel.userErrors',
        )

        result = self._extract(response, 'data.fulfillmentCancel.fulfillment', dict)
        self.set(**result)

        return self.status.is_cancelled

    def to_odoo_format(self):
        self.ensure_one()

        return dict(
            name=self.name,
            external_str_id=self.id_str,
            external_status=self.status.to_odoo_format(),
            external_order_str_id=self.order.id_str,
            tracking_number=', '.join(self.tracking_numbers),
            tracking_company=self.tracking_company,
            external_location_id=self.location.id_str,
            lines=[x.to_odoo_format() for x in self.fulfillment_line_items],
        )
