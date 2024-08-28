# See LICENSE file for full copyright and licensing details.

from typing import List
from collections import defaultdict

from .shopify_helpers import ShopifyOrderStatus


PAYMENT_NOT_DEFINED = 'Not_Defined'
SHOPIFY_ATTRIBUTE_PREF = 'shopify-attribute-'
SHOPIFY_ATTRIBUTE_VALUE_PREF = 'shopify-attribute-value-'
SHOPIFY_SHIPPING_PREF = 'shopify-shipping-'
SHOPIFY_PAYMENT_PREF = 'shopify-payment-'


def parse_attr_code(name):
    return name.replace(SHOPIFY_ATTRIBUTE_PREF, '')


def format_delivery_code(*args):
    if not any(args):
        return str()
    splitted_args = sum(map(lambda x: x.split(), args), [])
    name = ' '.join([arg.title() for arg in splitted_args])
    return f'{SHOPIFY_SHIPPING_PREF}{name}'


def format_attr_code(name):
    return f'{SHOPIFY_ATTRIBUTE_PREF}{name}'


def format_attr_value_code(option_name, option_value):
    return f'{SHOPIFY_ATTRIBUTE_VALUE_PREF}{option_name}-{option_value}'


def format_payment_code(name):
    if name:
        return f'{SHOPIFY_PAYMENT_PREF}{name}'
    return f'{SHOPIFY_PAYMENT_PREF}{PAYMENT_NOT_DEFINED}'


# TODO: the `price_set` parameter should be validated
def _get_price_in_customer_currency(price: float, price_set: dict, presentment_currency: str) -> float:
    """
    Return price based on the customer's currency.
    """
    shop_money = price_set.get('shop_money', {})
    presentment_money = price_set.get('presentment_money', {})

    if float(shop_money['amount']) > 0.0 and shop_money['currency_code'] == presentment_currency:
        price = shop_money['amount']
    elif float(presentment_money['amount']) > 0.0 and presentment_money['currency_code'] == presentment_currency:
        price = presentment_money['amount']

    return float(price)


# TODO: the `discount_data` parameter should be validated
def _calculate_discount(discount_data: dict, presentment_currency: str, use_customer_currency: str) -> float:
    total_discount = 0.0

    for discount_allocation in discount_data:
        discount_amount = float(discount_allocation.get('amount'))
        if use_customer_currency:
            discount_amount = _get_price_in_customer_currency(
                discount_amount,
                discount_allocation.get('amount_set'),
                presentment_currency,
            )
        total_discount += discount_amount

    return round(total_discount, 4)


class ShopifyOrderLine:

    def __init__(self, order: 'ShopifyOrder', data: dict) -> None:
        self._order = order
        self._data = data

    def __getattr__(self, name):
        return self._data.get(name)

    def __repr__(self):
        return f'<{self.integration.name}>: OrderLine({self.id})'

    @property
    def integration(self):
        return self._order.integration

    @property
    def env(self):
        return self._order.env

    @property
    def adapter(self):
        return self._order.adapter

    @property
    def id_str(self):
        return str(self.id)

    @property
    def taxes_included(self):
        return self._order.taxes_included

    @property
    def use_customer_currency(self):
        return self._order.use_customer_currency

    @property
    def presentment_currency(self):
        return self._order.presentment_currency

    def _parse_order_line(self, requested_quantity):
        price = float(self.price)
        if self.use_customer_currency:
            price = _get_price_in_customer_currency(price, self.price_set, self.presentment_currency)

        taxes = []
        if self.taxable:
            for tax in self.tax_lines:
                if not float(tax.get('price') or 0):
                    continue
                taxes.append(
                    self.adapter._format_tax(tax, self.taxes_included)
                )

        values = {
            'id': self.id_str,
            'price_unit': price,
            'product_uom_qty': requested_quantity,
            'product_id': self.adapter._build_product_external_code(self.product_id, self.variant_id),
            'discount': {},
            'price_unit_tax_incl': price if self.taxes_included else 0,
            'taxes': taxes,
        }

        # Parse discount
        if self.discount_allocations:
            amount = _calculate_discount(
                self.discount_allocations,
                self.presentment_currency,
                self.use_customer_currency,
            )
            if amount:
                amount_ = round(amount * requested_quantity / self.quantity, 4)

                values['discount'].update(
                    discount_amount=amount_,
                    discount_percent=100 * amount_ / (price or 1) / (requested_quantity or 1),
                    discount_amount_tax_incl=0,
                )

        return values


class ShopifyOrder:

    def __init__(
        self,
        integration,
        data: dict,
        fulfillment_orders: List[dict],
        order_risks: List[dict] = None,
        order_transactions: List[dict] = None,
    ) -> None:

        self.integration = integration
        self._data = data
        self._fulfillment_orders = fulfillment_orders
        self._order_risks = order_risks or []
        self._order_transactions = order_transactions or []
        self._lines = [ShopifyOrderLine(self, x) for x in data['line_items']]

        self._line_qty = defaultdict(list)

    def __repr__(self):
        return f'<{self.integration.name}>: Order({self.id})'

    def __getattr__(self, name):
        return self._data.get(name)

    @property
    def env(self):
        return self.integration.env

    @property
    def adapter(self):
        return self.integration.adapter

    @property
    def id_str(self):
        return str(self.id)

    @property
    def use_customer_currency(self):
        return self.integration.use_customer_currency

    @property
    def carrier(self):
        return self.shipping_lines and self.shipping_lines[0] or {}

    def parse(self):
        order_vals = {
            'id': self.id_str,
            'ref': self.name,
            'date_order': self.created_at,
            'lines': self.parse_lines(),
            'payment_method': self._parse_payment_code(self._data),
            'amount_total': self.get_price_total(),
            'delivery_data': self.parse_delivery_data(),
            'discount_data': {},  # Prestashop only
            'gift_data': {},
            'order_risks': self._order_risks,
            'order_transactions': self._order_transactions,
            'current_order_state': '',
            'external_tags': self._parse_tags(self._data),
            'is_cancelled': bool(self.cancel_reason),
            'external_location_id': self.location_id or False,
            'integration_workflow_states': self._parse_workflow_states(self._data),
            'currency': self.presentment_currency if self.use_customer_currency else self.currency,
            'order_fulfillments': [self.adapter._serialize_fulfillment(x) for x in self.fulfillments],
            'channel_id': self._parse_channel_id(self._data),
        }

        if self.customer:
            order_vals['customer'] = self.adapter._parse_customer(
                self.customer,
            )
            order_vals['shipping'] = self.adapter._parse_address(
                self.customer,
                self.shipping_address or {},
            )
            order_vals['billing'] = self.adapter._parse_address(
                self.customer,
                self.billing_address or {},
            )

        return order_vals

    def get_price_total(self):
        total_price = float(self.current_total_price)

        if self.use_customer_currency:
            return _get_price_in_customer_currency(
                total_price,
                self.current_total_price_set,
                self.presentment_currency,
            )

        return total_price

    def parse_lines(self):
        self._prepare_line_qty()
        lines_by_location = self._group_lines_by_location()

        parsed_lines = []
        for location_id, items in lines_by_location:
            for line_id, location_quantity in items:
                available_qty = self._get_available_line_qty(line_id)
                if available_qty <= 0:
                    continue

                if available_qty >= location_quantity:
                    requested_quantity = location_quantity
                else:
                    requested_quantity = available_qty

                self._update_line_qty(line_id, -requested_quantity)

                line = self._get_line_by_id(line_id)
                data = line._parse_order_line(requested_quantity)
                data['external_location_id'] = location_id

                parsed_lines.append(data)

        return parsed_lines

    def parse_delivery_data(self):
        """
        Parse original input file to get required delivery data
        """
        carrier = self.carrier
        carrier_title = carrier.get('title', '')
        carrier_code = carrier.get('code', '')

        carrier_data = dict()
        if carrier_title and carrier_code:
            carrier_data['name'] = carrier_title
            carrier_data['id'] = format_delivery_code(carrier_title, carrier_code)

        tax_list = [
            self.adapter._format_tax(tax, self.taxes_included) for tax in carrier.get('tax_lines', [])
        ]

        shipping_cost = carrier and float(carrier['price']) or 0
        if self.use_customer_currency and carrier:
            shipping_cost = _get_price_in_customer_currency(
                shipping_cost,
                carrier['price_set'],
                self.presentment_currency,
            )

        delivery_notes = self.note or ''

        # Calculate total discount if any
        discount = dict()
        if carrier.get('discount_allocations'):
            amount = _calculate_discount(
                carrier['discount_allocations'],
                self.presentment_currency,
                self.use_customer_currency,
            )

            if amount:
                discount.update(
                    discount_amount=amount,
                    discount_percent=100 * amount / (shipping_cost or 1),
                    discount_amount_tax_incl=0,
                )

        return {
            'carrier': carrier_data,
            'shipping_cost': shipping_cost,
            'taxes': tax_list,
            'delivery_notes': delivery_notes,
            'discount': discount,
        }

    def _get_line_by_id(self, line_id):
        return {x.id_str: x for x in self._lines}[str(line_id)]

    def _prepare_line_qty(self):
        # 1. Clear old values
        self._line_qty.clear()

        # 1.1 Add quantities from the all lines
        for line in self._lines:
            self._update_line_qty(line.id_str, line.quantity)

        # 1.2 Subtract the quantities from refunds
        for refund in self.refunds:
            for ref_line in refund['refund_line_items']:
                self._update_line_qty(str(ref_line['line_item_id']), -ref_line['quantity'])

    def _get_available_line_qty(self, line_id):
        return sum(self._line_qty.get(line_id, []))

    def _update_line_qty(self, line_id, qty):
        self._line_qty[line_id].append(qty)

    def _group_lines_by_location(self):
        result = []
        for order in filter(lambda x: x['line_items'] and x['status'] != 'cancelled', self._fulfillment_orders):
            line_items = order['line_items']

            if order['status'] == 'closed':
                if all(x['fulfillable_quantity'] for x in line_items):
                    continue
                line_items = list(filter(lambda x: not x['fulfillable_quantity'], line_items))

            items = [(str(x['line_item_id']), x['quantity']) for x in line_items if x['quantity']]

            if items:
                result.append(
                    (str(order['assigned_location_id']), items)
                )

        return result

    @staticmethod
    def _parse_workflow_states(data):
        """
        Order of the `financial_status` (1)
        and 'fulfillment_status' (2) matters
        """

        fulfillment_status = data['fulfillment_status']
        if not fulfillment_status:
            # TODO: seems here we need to add also the status `unshipped`
            # due to the `null` value relates to `unshipped` status as well
            fulfillment_status = ShopifyOrderStatus.STATUS_UNFULFILLED

        return [
            data['financial_status'],
            fulfillment_status,
        ]

    @staticmethod
    def _parse_payment_code(data):
        pay_code_list = data.get('payment_gateway_names', [])
        name = pay_code_list and pay_code_list[0] or None
        return format_payment_code(name)

    @staticmethod
    def _parse_tags(data):
        tag_string = data.get('tags', '')
        if not tag_string:
            return list()
        return list(set(x.strip() for x in tag_string.split(',')))

    @staticmethod
    def _parse_channel_id(data):
        return data.get('channel_id', '') or ''
