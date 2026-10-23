# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase


def _money_bag(amount):
    money = {'amount': amount, 'currencyCode': 'EUR'}
    return {'shopMoney': money, 'presentmentMoney': money}


def _tax_line(amount):
    return {
        'title': 'DE MwSt',
        'rate': 0.19,
        'ratePercentage': 19.0,
        'source': 'Shopify',
        'priceSet': _money_bag(amount),
    }


def _allocation(amount, title='SUBS-FREE-SHIP'):
    return {
        'allocatedAmountSet': _money_bag(amount),
        'discountApplication': {'title': title},
    }


def _shipping_line(line_id, original, discounted, title='Standardversand DE', taxes=(), allocations=(),
                   is_removed=False):
    """A real shipping line, as returned by the `shippingLines` connection."""
    return {
        'id': 'gid://shopify/ShippingLine/%s' % line_id,
        'title': title,
        'code': title,
        'isRemoved': is_removed,
        'carrierIdentifier': None,
        'originalPriceSet': _money_bag(original),
        'currentDiscountedPriceSet': _money_bag(discounted),
        'taxLines': list(taxes),
        'discountAllocations': list(allocations),
    }


def _shipping_summary(title, original, discounted):
    """The line Shopify synthesizes in `Order.shippingLine` when the order has several shipping lines.

    Prices are summed and titles joined, but there is no id or code, and tax lines and discount
    allocations are always empty.
    """
    return {
        'id': None,
        'title': title,
        'code': None,
        'isRemoved': False,
        'carrierIdentifier': None,
        'originalPriceSet': _money_bag(original),
        'currentDiscountedPriceSet': _money_bag(discounted),
        'taxLines': [],
        'discountAllocations': [],
    }


def _fulfillment_order(order_id, status, service_code, presented_name, line_quantities=None):
    line_items = [
        {'id': 'gid://shopify/FulfillmentOrderLineItem/%s' % order_id, 'totalQuantity': total,
         'remainingQuantity': remaining}
        for total, remaining in (line_quantities or [])
    ]
    return {
        'id': 'gid://shopify/FulfillmentOrder/%s' % order_id,
        'status': status,
        'lineItems': {'nodes': line_items},
        'deliveryMethod': {
            'id': 'gid://shopify/DeliveryMethod/%s' % order_id,
            'methodType': 'SHIPPING',
            'serviceCode': service_code,
            'presentedName': presented_name,
        },
    }


def _order(shipping_line, shipping_lines, fulfillment_orders=()):
    return {
        'id': 'gid://shopify/Order/1',
        'taxesIncluded': True,
        'taxExempt': False,
        'note': None,
        'shippingLine': shipping_line,
        'shippingLines': {'nodes': list(shipping_lines)},
        'fulfillmentOrders': {'nodes': list(fulfillment_orders)},
    }


@tagged('post_install', '-at_install', 'test_shopify_shipping_discount')
class TestShopifyShippingDiscount(IntegrationShopifyBase):
    """Delivery data parsed from orders with several shipping lines.

    Shopify returns a synthesized summary in `Order.shippingLine` for such orders (summed prices, joined
    titles, no tax lines and no discount allocations), so taxes and discounts have to come from the real
    lines of the `shippingLines` connection. The carrier must ignore fulfillment orders that were
    cancelled or closed before anything shipped, as the order lines already do.
    """

    def _parse_delivery_data(self, order_data):
        order = self.adapter.gql.Order.set(**order_data)
        return order.parse_delivery_data()

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def test_free_shipping_discount_on_order_with_two_shipping_lines_is_parsed(self):
        """Order #380784 shape: a 6.50 line fully discounted by a free-shipping code plus a 0.00 duplicate.

        Without the discount the framework reconciles the order with a "rounding" line of -6.50.
        """
        order_data = _order(
            _shipping_summary('Standardversand DE', '6.5', '0.0'),
            [
                _shipping_line(1, '6.5', '0.0', allocations=[_allocation('6.5')]),
                _shipping_line(2, '0.0', '0.0', allocations=[_allocation('0.0')]),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(result['shipping_cost'], 6.5, 'Shipping cost is the pre-discount price')
        self.assertEqual(
            result['discount'],
            {
                'discount_allocations': [
                    {'code': 'SUBS-FREE-SHIP', 'discount_amount': 6.5, 'discount_amount_tax_incl': 0},
                ],
                'discount_amount': 6.5,
                'discount_percent': 100.0,
            },
            'The free-shipping allocation must be taken from the real shipping lines',
        )

    def test_discounts_of_all_shipping_lines_are_summed(self):
        order_data = _order(
            _shipping_summary('Line A and Line B', '15.0', '9.0'),
            [
                _shipping_line(1, '10.0', '6.0', title='Line A', allocations=[_allocation('4.0', 'SPRING')]),
                _shipping_line(2, '5.0', '3.0', title='Line B', allocations=[_allocation('2.0', 'SPRING')]),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(result['shipping_cost'], 15.0)
        self.assertEqual(result['discount'].get('discount_amount'), 6.0, 'Allocations of every line are summed')
        self.assertEqual(result['discount'].get('discount_percent'), 40.0)

    def test_single_shipping_line_discount_is_parsed(self):
        """Regression guard: with one shipping line the summary is the line itself, and nothing may change."""
        line = _shipping_line(1, '6.5', '0.0', allocations=[_allocation('6.5')])
        order_data = _order(line, [line])

        result = self._parse_delivery_data(order_data)

        self.assertEqual(result['shipping_cost'], 6.5)
        self.assertEqual(result['discount']['discount_amount'], 6.5)
        self.assertEqual(result['discount']['discount_percent'], 100.0)

    def test_discount_allocated_to_removed_shipping_line_is_ignored(self):
        """A removed shipping line is not billed, so its allocation must not become a discount."""
        order_data = _order(
            _shipping_summary('Standardversand DE', '6.5', '6.5'),
            [
                _shipping_line(1, '6.5', '6.5'),
                _shipping_line(2, '4.0', '0.0', allocations=[_allocation('4.0')], is_removed=True),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(result['discount'], {}, 'Only live shipping lines may contribute a discount')

    # ------------------------------------------------------------------
    # Taxes
    # ------------------------------------------------------------------

    def test_shipping_taxes_on_order_with_two_shipping_lines_are_parsed(self):
        order_data = _order(
            _shipping_summary('Line A and Line B', '15.0', '15.0'),
            [
                _shipping_line(1, '10.0', '10.0', title='Line A', taxes=[_tax_line('1.9')]),
                _shipping_line(2, '5.0', '5.0', title='Line B', taxes=[_tax_line('0.95')]),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(
            set(result['taxes']),
            {'DE MwSt 19.0% [included]'},
            'Tax lines must be taken from the real shipping lines, the summary line has none',
        )

    # ------------------------------------------------------------------
    # Carrier
    # ------------------------------------------------------------------

    def test_cancelled_fulfillment_order_does_not_provide_the_carrier(self):
        order_data = _order(
            _shipping_summary('Express Delivery', '6.5', '6.5'),
            [_shipping_line(1, '6.5', '6.5', title='Express Delivery')],
            fulfillment_orders=[
                _fulfillment_order(1, 'CANCELLED', 'ups-ground', 'UPS Ground'),
                _fulfillment_order(2, 'OPEN', 'dhl-paket', 'DHL Paket'),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(
            result['carrier']['name'],
            'DHL Paket',
            'The carrier of a cancelled fulfillment order must not be used',
        )

    def test_fulfillment_order_closed_before_fulfillment_does_not_provide_the_carrier(self):
        order_data = _order(
            _shipping_summary('Express Delivery', '6.5', '6.5'),
            [_shipping_line(1, '6.5', '6.5', title='Express Delivery')],
            fulfillment_orders=[
                _fulfillment_order(1, 'CLOSED', 'ups-ground', 'UPS Ground', line_quantities=[(1, 1)]),
                _fulfillment_order(2, 'OPEN', 'dhl-paket', 'DHL Paket'),
            ],
        )

        result = self._parse_delivery_data(order_data)

        self.assertEqual(
            result['carrier']['name'],
            'DHL Paket',
            'A fulfillment order closed with nothing shipped must not provide the carrier',
        )
