# See LICENSE file for full copyright and licensing details.

from types import SimpleNamespace

from .base import ShopifyResourceUpdate
from .metafields_mixin import MetafieldMixin


class OrderParseMixin:

    def __init__(self, *args, **kwargs):
        self._props = SimpleNamespace(
            use_customer_currency=False,
        )
        self._order_line_items = []

    @property
    def props(self):
        return self._props

    @property
    def order_line_items(self):
        self.ensure_one()

        if not self._order_line_items:
            for data in (self['lineItems'] or []):
                line = self._env.OrderLineItem.set(**data)
                line._order = self

                self._order_line_items.append(line)

        return self._order_line_items

    def update_props(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self.props, key, value)

    def parse(self, **kwargs):
        self.ensure_one()

        # 0. Update props
        self.update_props(**kwargs)

        # 1. Parse order values
        lines = self.parse_lines()
        payment_method = self.parse_payment_method()
        payment_methods = self.parse_payment_gateway_names()
        amount_total = self.parse_price_total()
        delivery_data = self.parse_delivery_data()
        order_risks = self.parse_order_risks()
        payment_transactions = self.parse_payment_transactions()
        integration_workflow_states = self.parse_workflow_states()
        currency_code = self.parse_currency_code()
        order_fulfillments = self.parse_fulfillments()
        sale_channel_data = self.parse_sale_channel()
        customer_data = self.parse_customer_data()

        return {
            'id': self.id_str,
            'ref': self.name,
            'date_order': self.created_at,
            'lines': lines,
            'payment_method': payment_method,
            'payment_methods': payment_methods,
            'amount_total': amount_total,
            'delivery_data': delivery_data,
            'discount_data': {},  # Prestashop only
            'gift_data': {},
            'order_risks': order_risks,
            'payment_transactions': payment_transactions,
            'current_order_state': '',
            'external_tags': self.tags,
            'is_cancelled': self.is_cancelled,
            'external_location_id': self.location_id,
            'integration_workflow_states': integration_workflow_states,
            'currency': currency_code,
            'order_fulfillments': order_fulfillments,
            'sale_channel_data': sale_channel_data,
            'order_source_name': self.source_name,
            **customer_data,
        }

    def parse_lines(self):
        self.ensure_one()

        # 1. Reset the quantity to the original value
        for line in self.order_line_items:
            line.drop_key('current_quantity_tmp')

        # 2. Group lines by location
        lines_by_location = self._group_lines_by_location()

        # 3. Parse line accouring to location requested quantity
        result = []
        for location_id, items in lines_by_location:
            for (order_line_id, fulfillment_order_qty) in items:
                order_line = self._get_order_line_by_id(order_line_id)

                available_qty = order_line.current_quantity_tmp
                if available_qty <= 0:
                    continue

                fulfillment_order_qty = order_line.current_quantity_tmp
                requested_qty = fulfillment_order_qty if (available_qty >= fulfillment_order_qty) else available_qty
                order_line.set(current_quantity_tmp=available_qty - requested_qty)

                data = order_line.parse(requested_qty)
                data['external_location_id'] = location_id

                result.append(data)

        return result

    def parse_payment_gateway_names(self) -> list:
        self.ensure_one()

        names = self.payment_gateway_names
        OrderTransaction = self._env.OrderTransaction.cls

        if not names:
            return [OrderTransaction.format_payment_code(False)]
        return [OrderTransaction.format_payment_code(x) for x in names]

    def parse_payment_method(self):
        return self.parse_payment_gateway_names()[-1]

    def parse_price_total(self):
        money_bag = self.current_total_price_set
        return money_bag.get_amount(self.props.use_customer_currency)

    def parse_delivery_data(self):
        shipping_line = self.shipping_line
        delivery_method = self.delivery_method

        carrier, shipping_cost, taxes, note = {}, 0, [], ''

        if (shipping_line and delivery_method and delivery_method.is_valid):
            carrier = delivery_method.to_odoo_format()
            shipping_cost = shipping_line.get_price(self.props.use_customer_currency)
            taxes = [x.to_odoo_format(self.is_taxable) for x in shipping_line.tax_lines]
            note = self.note or ''

        return {
            'carrier': carrier,
            'shipping_cost': shipping_cost,
            'taxes': taxes,
            'delivery_notes': note,
            'discount': {},  # Discount already included in the shipping cost
            # TODO: add discount data if it's essential to see the discount value right in the delivery-order-line
        }

    def parse_order_risks(self, risklevel: str = 'HIGH'):
        self.ensure_one()

        result = self.risk_summary.parse(risklevel=risklevel)

        for risk in result:
            risk['order_id'] = self.id_str

        return result

    def parse_payment_transactions(self):
        use_customer_currency = self.props.use_customer_currency
        return [x.to_odoo_format(use_customer_currency) for x in self.transactions]

    def parse_workflow_states(self):
        """
        Order of the `financial_status` (1)
        and `fulfillment_status` (2) matters!!!
        """
        self.ensure_one()

        return [
            self.financial_status.to_odoo_format(),
            self.fulfillment_status.to_odoo_format(),
        ]

    def parse_currency_code(self):
        self.ensure_one()
        return self.presentmentCurrencyCode if self.props.use_customer_currency else self.currencyCode

    def parse_fulfillments(self):
        self.ensure_one()
        return [x.to_odoo_format() for x in self.fulfillments]

    def parse_sale_channel(self):
        self.ensure_one()
        publication = self.publication

        if not publication:
            return None

        return publication.to_odoo_format()

    def parse_customer_data(self):
        self.ensure_one()
        customer = self.customer

        if customer:
            billing = self.billing_address

            if billing:
                billing_data_ = billing.to_odoo_format()
            else:
                billing_data_ = customer.parse_default_address()

            if self.billing_matches_shipping:
                shipping_data_ = billing_data_
            else:
                shipping = self.shipping_address

                if shipping:
                    shipping_data_ = shipping.to_odoo_format()
                else:
                    shipping_data_ = customer.parse_default_address()

            customer_data = customer.to_odoo_format()
            billing_data = customer._update_with_defaults(billing_data_, type='invoice')
            shipping_data = customer._update_with_defaults(shipping_data_)
        else:
            customer_data = billing_data = shipping_data = {}

        return {
            'customer': customer_data,
            'billing': billing_data,
            'shipping': shipping_data,
        }


class Order(ShopifyResourceUpdate, MetafieldMixin, OrderParseMixin):

    _gid_name = 'Order'
    _request_name = 'order'
    _body = ShopifyResourceUpdate._tmpl.ORDER_BODY

    ORDER_GET_TAXES_BODY = ShopifyResourceUpdate._tmpl.ORDER_GET_TAXES_BODY
    ORDER_GET_PAYMENT_METHODS_BODY = ShopifyResourceUpdate._tmpl.ORDER_GET_PAYMENT_METHODS_BODY
    ORDER_INPUT_FILE_BODY = ShopifyResourceUpdate._tmpl.ORDER_INPUT_FILE_BODY

    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_ORDER
    MUTATION_CANCEL_ORDER = ShopifyResourceUpdate._tmpl.MUTATION_CANCEL_ORDER
    MUTATION_MARK_AS_PAID = ShopifyResourceUpdate._tmpl.MUTATION_MARK_AS_PAID

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        OrderParseMixin.__init__(self, *args, **kwargs)

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'data': self.to_dict(),
            'updated_at': self.updated_at,
            'created_at': self.created_at,
        }

    @property
    def is_cancelled(self):
        self.ensure_one()
        return bool(self.cancelledAt)

    @property
    def is_taxable(self):
        self.ensure_one()
        return self['taxesIncluded'] and not self['taxExempt']

    @property
    def requires_shipping(self):
        self.ensure_one()
        return self['requiresShipping']

    @property
    def source_name(self):
        self.ensure_one()
        return self['sourceName'] or ''

    @property
    def fulfillment_status(self):
        self.ensure_one()
        status = self['displayFulfillmentStatus']

        if not status:
            return self._env.OrderDisplayFulfillmentStatus('UNFULFILLED')

        return self._env.OrderDisplayFulfillmentStatus(status)

    @property
    def financial_status(self):
        self.ensure_one()
        return self._env.OrderDisplayFinancialStatus(self['displayFinancialStatus'])

    @property
    def risk_summary(self):
        self.ensure_one()
        return self._env.OrderRiskSummary.set(**(self['risk'] or {}))

    @property
    def current_total_price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['currentTotalPriceSet'] or {}))

    @property
    def payment_gateway_names(self):
        self.ensure_one()
        return self.paymentGatewayNames or []

    @property
    def line_items(self):
        self.ensure_one()
        return [self._env.LineItem.set(**x) for x in (self['lineItems'] or [])]

    @property
    def tax_lines(self):
        self.ensure_one()
        return [self._env.TaxLine.set(**x) for x in (self['taxLines'] or [])]

    @property
    def customer(self):
        self.ensure_one()
        return self._env.Customer.set(**(self['customer'] or {}))

    @property
    def transactions(self):
        self.ensure_one()
        return [self._env.OrderTransaction.set(**x) for x in (self['transactions'] or [])]

    @property
    def fulfillment_orders(self):
        self.ensure_one()

        if not self.key_exist('fulfillmentOrders'):
            self.get_fulfillment_orders()

        return [self._env.FulfillmentOrder.set(**x) for x in (self['fulfillmentOrders'] or [])]

    @property
    def fulfillments(self):
        self.ensure_one()

        if not self.key_exist('fulfillments'):
            self.get_fulfillments()

        return [self._env.Fulfillment.set(**x) for x in (self['fulfillments'] or [])]

    @property
    def shipping_line(self):
        self.ensure_one()
        return self._env.ShippingLine.set(**(self['shippingLine'] or {}))

    @property
    def shipping_lines(self):
        self.ensure_one()
        return [self._env.ShippingLine.set(**x) for x in (self['shippingLines'] or [])]

    @property
    def billing_address(self):
        self.ensure_one()
        return self._env.MailingAddress.set(**(self['billingAddress'] or {}))

    @property
    def shipping_address(self):
        self.ensure_one()
        return self._env.MailingAddress.set(**(self['shippingAddress'] or {}))

    @property
    def delivery_method(self):
        self.ensure_one()

        fulfillment_orders = self.fulfillment_orders
        default_delivery_method = self._env.DeliveryMethod

        if not fulfillment_orders:
            return default_delivery_method

        shipping_code = self.shipping_line['code']

        if not shipping_code:
            return default_delivery_method

        fulfillment_order = next(
            filter(lambda x: x.delivery_method.code == shipping_code, fulfillment_orders),
            None,
        )

        if not fulfillment_order:
            return default_delivery_method

        return fulfillment_order.delivery_method

    @property
    def publication(self):
        self.ensure_one()
        return self._env.Publication.set(**(self['publication'] or {}))

    @property
    def location_id(self):
        self.ensure_one()
        fulfillment_orders = self.fulfillment_orders

        if len(fulfillment_orders) != 1:
            return False

        return fulfillment_orders[0].location.id_str

    @property
    def billing_matches_shipping(self):
        self.ensure_one()
        return self.billingAddressMatchesShippingAddress

    def get_batch_body_minimal(self, filter_params: str = ''):
        return self.get_batch(
            body=self.ORDER_INPUT_FILE_BODY,
            arguments='sortKey: CREATED_AT',
            filter_params=filter_params,
        )

    def get_batch_for_payment_methods(self):
        return self.get_batch(
            body=self.ORDER_GET_PAYMENT_METHODS_BODY,
            arguments='sortKey: ID, reverse: true',
        )

    def get_batch_for_taxes(self):
        return self.get_batch(
            body=self.ORDER_GET_TAXES_BODY,
            arguments='sortKey: ID, reverse: true',
        )

    def update(self, **kwargs: dict) -> bool:
        self.ensure_one()

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'input': {
                    'id': self.gid,
                    **kwargs,
                },
            },
            user_errors_path='data.orderUpdate.userErrors',
        )

        result = self._extract(response, 'data.orderUpdate.order', dict)
        self.set(**result)

        return True

    def cancel(self, *args):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_CANCEL_ORDER % (self.id, *args),
            user_errors_path='data.orderCancel.orderCancelUserErrors',
        )

        result = self._extract(response, 'data.orderCancel.job', dict)

        return result

    def _get_order_line_by_id(self, line_id: str):
        return {x.id_str: x for x in self.order_line_items}[line_id]

    def _get_available_line_qty(self, line_id):
        return sum(self._line_qty.get(line_id, []))

    def _group_lines_by_location(self):
        result = []
        for f_order in self.fulfillment_orders:
            if f_order.is_cancelled or not f_order.line_items:
                continue

            line_items = f_order.line_items

            if f_order.is_closed:
                if f_order.closed_before_fulfill:
                    continue
                line_items = filter(lambda x: not x.remaining_quantity, line_items)

            items = [(x.sale_line_item.id_str, x.total_quantity) for x in line_items if x.total_quantity]

            if items:
                result.append((f_order.location.id_str, items))

        return result

    def get_fulfillment_orders(self, open_or_in_progress=False):
        self.ensure_one()

        body = 'id fulfillmentOrders(first: 25) { nodes { %s } }' % self._env.FulfillmentOrder.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(fulfillmentOrders=result['fulfillmentOrders'])

        orders = self.fulfillment_orders

        if open_or_in_progress:
            return [x for x in orders if x.status.open_or_in_progress and x.line_items]

        return orders

    def get_fulfillments(self):
        self.ensure_one()

        body = 'id fulfillments(first: 25) { %s }' % self._env.Fulfillment.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(fulfillments=result['fulfillments'])

        return self.fulfillments

    def mark_as_paid(self):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_MARK_AS_PAID,
            variables={
                'input': {
                    'id': self.gid,
                },
            },
            user_errors_path='data.orderMarkAsPaid.userErrors',
        )

        result = self._extract(response, 'data.orderMarkAsPaid.order', dict)
        self.set(**result)

        return True
