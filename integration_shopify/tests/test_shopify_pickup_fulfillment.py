# See LICENSE file for full copyright and licensing details.

from unittest import skip
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase
from ..shopify.exceptions import ShopifyApiError
from ..shopify.resources.fulfillment_order import FulfillmentOrder
from ..shopify.resources.order import Order

SHIPPING_CODE = 'shopify-shipping-Standard Dpd'
SKIP_NON_SHIPPING_CODE = (
    'The "Shopify Code" is required for every carrier for now: the check that lets pickup and local delivery '
    'go without it is commented out in `DeliveryCarrier.get_external_carrier_code`'
)


def _fulfillment_order(order_id, location_id, method_type, lines, status='OPEN'):
    """A fulfillment order with the given `lines`: a list of (sale line id, quantity) pairs."""
    return {
        'id': 'gid://shopify/FulfillmentOrder/%s' % order_id,
        'status': status,
        'assignedLocation': {'location': {'id': 'gid://shopify/Location/%s' % location_id}},
        'deliveryMethod': {
            'id': 'gid://shopify/DeliveryMethod/%s' % order_id,
            'methodType': method_type,
            'serviceCode': 'Some code',
            'presentedName': 'Some name',
        },
        'lineItems': {
            'nodes': [
                {
                    'id': 'gid://shopify/FulfillmentOrderLineItem/%s%s' % (order_id, line_id),
                    'totalQuantity': qty,
                    'remainingQuantity': qty,
                    'lineItem': {'id': 'gid://shopify/LineItem/%s' % line_id},
                }
                for line_id, qty in lines
            ],
        },
    }


@tagged('post_install', '-at_install', 'test_shopify_pickup_fulfillment')
class TestShopifyPickupFulfillmentOrders(IntegrationShopifyBase):
    """Fulfillment orders are matched to a picking by location, and the ones in another location are moved.

    A pickup fulfillment order is tied to the store the customer chose, so it must never be moved to
    the location of the warehouse the goods happened to be picked in. An order for a pickup point is
    shipped there, so it is moved like a shipping one.
    """

    def _prepare(self, fulfillment_orders, picking_location, lines):
        orders = [self.adapter.gql.FulfillmentOrder.set(**x) for x in fulfillment_orders]
        picking_data = {
            'external_location_id': picking_location,
            'lines': [{'id': line_id, 'qty': qty} for line_id, qty in lines],
        }

        with patch.object(FulfillmentOrder, 'move', autospec=True) as move, \
                patch.object(FulfillmentOrder, 'split', autospec=True) as split:
            moved = self.adapter._prepare_fulfillment_orders(orders, picking_data)

        return moved, move, split

    def test_pickup_fulfillment_order_is_not_moved_to_the_picking_location(self):
        pickup = _fulfillment_order(1, location_id=111, method_type='PICK_UP', lines=[(100, 3)])

        moved, move, split = self._prepare([pickup], picking_location=222, lines=[(100, 3)])

        self.assertFalse(moved, 'Nothing may be reported as moved')
        move.assert_not_called()
        split.assert_not_called()

    def test_pickup_point_fulfillment_order_is_moved_to_the_picking_location(self):
        """The goods travel to a pickup point, so such an order is a shipment like any other."""
        pickup_point = _fulfillment_order(1, location_id=111, method_type='PICKUP_POINT', lines=[(100, 3)])

        moved, move, split = self._prepare([pickup_point], picking_location=222, lines=[(100, 3)])

        self.assertTrue(moved)
        move.assert_called_once()
        self.assertEqual(move.call_args.args[1], 222)
        split.assert_not_called()

    def test_pickup_fulfillment_order_is_not_split_to_be_moved(self):
        pickup = _fulfillment_order(1, location_id=111, method_type='PICK_UP', lines=[(100, 3), (101, 2)])

        moved, move, split = self._prepare([pickup], picking_location=222, lines=[(100, 3)])

        self.assertFalse(moved)
        move.assert_not_called()
        split.assert_not_called()

    def test_shipping_fulfillment_order_is_moved_to_the_picking_location(self):
        """Regression guard: moving shipping fulfillment orders is the feature that must keep working."""
        shipping = _fulfillment_order(1, location_id=111, method_type='SHIPPING', lines=[(100, 3)])

        moved, move, split = self._prepare([shipping], picking_location=222, lines=[(100, 3)])

        self.assertTrue(moved)
        move.assert_called_once()
        self.assertEqual(move.call_args.args[1], 222)
        split.assert_not_called()

    def test_local_delivery_fulfillment_order_is_moved_to_the_picking_location(self):
        """Local delivery is dispatched from a location, so unlike a pickup it may be re-assigned."""
        local = _fulfillment_order(1, location_id=111, method_type='LOCAL', lines=[(100, 3)])

        moved, move, split = self._prepare([local], picking_location=222, lines=[(100, 3)])

        self.assertTrue(moved)
        move.assert_called_once()

    def test_shipping_is_moved_but_pickup_stays_in_an_order_with_both(self):
        """One order with a shipping and a pickup fulfillment order, all picked in the same warehouse."""
        shipping = _fulfillment_order(1, location_id=111, method_type='SHIPPING', lines=[(100, 2)])
        pickup = _fulfillment_order(2, location_id=333, method_type='PICK_UP', lines=[(101, 1)])

        moved, move, split = self._prepare(
            [shipping, pickup],
            picking_location=222,
            lines=[(100, 2), (101, 1)],
        )

        self.assertTrue(moved, 'The shipping fulfillment order has to be moved')
        move.assert_called_once()
        moved_order = move.call_args.args[0]
        self.assertEqual(moved_order.id_str, '1', 'Only the shipping fulfillment order is moved')
        split.assert_not_called()


@tagged('post_install', '-at_install', 'test_shopify_pickup_fulfillment')
class TestShopifyCarrierCodeForPickup(IntegrationShopifyBase):
    """The "Shopify Code" is the tracking company, so only carriers that can ship a parcel need it."""

    def _carrier(self, external_code):
        product = self.env['product.product'].create({'name': 'Delivery %s' % external_code, 'type': 'service'})
        carrier = self.env['delivery.carrier'].create({
            'name': 'Carrier %s' % external_code,
            'product_id': product.id,
        })
        external = self.env['integration.delivery.carrier.external'].create({
            'integration_id': self.integration.id,
            'name': 'External %s' % external_code,
            'code': external_code,
        })
        self.env['integration.delivery.carrier.mapping'].create({
            'integration_id': self.integration.id,
            'carrier_id': carrier.id,
            'external_carrier_id': external.id,
        })

        return carrier

    @skip(SKIP_NON_SHIPPING_CODE)
    def test_pickup_carrier_without_shopify_code_exports_without_tracking_company(self):
        carrier = self._carrier('PICK_UP')

        self.assertEqual(carrier.get_external_carrier_code(self.integration), '')

    @skip(SKIP_NON_SHIPPING_CODE)
    def test_local_delivery_carrier_without_shopify_code_exports_without_tracking_company(self):
        carrier = self._carrier('LOCAL')

        self.assertEqual(carrier.get_external_carrier_code(self.integration), '')

    def test_shipping_carrier_without_shopify_code_still_requires_it(self):
        """Regression guard: a carrier that ships parcels needs a tracking company the customer recognises."""
        carrier = self._carrier(SHIPPING_CODE)

        with self.assertRaises(UserError):
            carrier.get_external_carrier_code(self.integration)

    def test_pickup_carrier_with_shopify_code_returns_it(self):
        carrier = self._carrier('PICK_UP')
        carrier.shopify_code = 'other'

        self.assertEqual(carrier.get_external_carrier_code(self.integration), 'other')


@tagged('post_install', '-at_install', 'test_shopify_pickup_fulfillment')
class TestShopifyPickupPreparedForPickup(IntegrationShopifyBase):
    """A validated pickup picking marks the goods ready for pickup instead of fulfilling the order.

    Shopify closes a pickup fulfillment order only when the customer collects the goods, which the
    merchant records in Shopify. Fulfilling it from Odoo would send the "picked up" receipt at once. The
    mutation takes a whole fulfillment order, so a picking covering only a part of it first splits that
    part off into a fulfillment order of its own.
    """

    LOCATION = 111
    ALREADY_PREPARED = {
        'message': 'The fulfillment order does not have any line items that can be prepared.',
        'code': 'NO_LINE_ITEMS_TO_PREPARE_FOR_FULFILLMENT_ORDER',
    }

    def _fake_execute(self, prepare_errors=()):
        """A Shopify stand-in that records the mutations and answers the split and prepare ones."""
        calls = []

        def execute(query, variables=None, user_errors_path=''):
            calls.append((query, variables))

            if 'fulfillmentOrderSplit(' in query:
                split_off = _fulfillment_order(900, self.LOCATION, 'PICK_UP', [(100, 2)])
                return {'data': {'fulfillmentOrderSplit': {
                    'fulfillmentOrderSplits': [{'remainingFulfillmentOrder': split_off}],
                    'userErrors': [],
                }}}

            if 'fulfillmentOrderLineItemsPreparedForPickup(' in query:
                if prepare_errors:
                    raise ShopifyApiError(str(list(prepare_errors)))

                return {'data': {'fulfillmentOrderLineItemsPreparedForPickup': {'userErrors': []}}}

            raise AssertionError('Unexpected request: %s' % query)

        return execute, calls

    PICKING_ID = 77

    def _send(self, fulfillment_orders, lines, prepare_errors=()):
        orders = [self.adapter.gql.FulfillmentOrder.set(**x) for x in fulfillment_orders]
        picking_data = {
            'picking_id': self.PICKING_ID,
            'external_location_id': self.LOCATION,
            'lines': [{'id': line_id, 'qty': qty} for line_id, qty in lines],
            'carrier_code': '',
            'tracking': '',
            'carrier_tracking_url': '',
        }
        execute, calls = self._fake_execute(prepare_errors)
        fulfillment = MagicMock()
        fulfillment.to_odoo_format.return_value = {'id': 'fulfillment'}

        # Every resource builds its own client, so the requests are caught on the resource class
        with patch.object(Order, 'get_fulfillment_orders', return_value=orders), \
                patch.object(FulfillmentOrder, 'execute', side_effect=execute), \
                patch.object(FulfillmentOrder, 'fulfill', return_value=fulfillment) as fulfill:
            result = self.adapter.send_picking('gid://shopify/Order/1', picking_data)

        prepared = [x for x in calls if 'fulfillmentOrderLineItemsPreparedForPickup(' in x[0]]
        splits = [x for x in calls if 'fulfillmentOrderSplit(' in x[0]]

        return result, fulfill, prepared, splits

    def _ready_report(self, *ids):
        """What the export reports for a picking whose goods are in the given ready fulfillment orders."""
        return [{'picking_id': self.PICKING_ID, 'prepared_fulfillment_order_ids': list(ids)}]

    @staticmethod
    def _prepared_ids(prepared):
        return [
            x['fulfillmentOrderId']
            for _query, variables in prepared
            for x in variables['input']['lineItemsByFulfillmentOrder']
        ]

    def test_picking_covering_the_whole_pickup_fulfillment_order_marks_it_ready_for_pickup(self):
        pickup = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)])

        result, fulfill, prepared, splits = self._send([pickup], lines=[(100, 4)])

        self.assertEqual(self._prepared_ids(prepared), ['gid://shopify/FulfillmentOrder/1'])
        self.assertFalse(splits, 'The whole fulfillment order is prepared, nothing is split off')
        fulfill.assert_not_called()
        self.assertEqual(
            result, self._ready_report('1'),
            'No Shopify fulfillment exists until the customer collects the goods, only the ready fulfillment order',
        )

    def test_picking_covering_a_part_of_the_pickup_fulfillment_order_splits_that_part_off(self):
        pickup = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)])

        result, fulfill, prepared, splits = self._send([pickup], lines=[(100, 2)])

        self.assertEqual(len(splits), 1)
        split_lines = splits[0][1]['fulfillmentOrderSplits'][0]['fulfillmentOrderLineItems']
        self.assertEqual([x['quantity'] for x in split_lines], [2])
        self.assertEqual(
            self._prepared_ids(prepared),
            ['gid://shopify/FulfillmentOrder/900'],
            'Only the part that was split off may be marked ready, the rest is not prepared yet',
        )
        fulfill.assert_not_called()
        self.assertEqual(result, self._ready_report('900'), 'The picking holds the part that was split off')

    def test_pickup_picking_for_goods_already_marked_ready_is_not_an_error(self):
        """Shopify refuses to prepare a fulfillment order a second time, which only means it is already ready."""
        pickup = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)])

        result, fulfill, prepared, splits = self._send(
            [pickup],
            lines=[(100, 4)],
            prepare_errors=[self.ALREADY_PREPARED],
        )

        self.assertEqual(len(prepared), 1)
        self.assertEqual(result, self._ready_report('1'))

    def test_pickup_fulfillment_order_the_merchant_already_marked_ready_is_left_alone(self):
        """A prepared fulfillment order is `IN_PROGRESS` and Shopify offers no split for it any more.

        That is how it looks when the merchant pressed "Ready for pickup" in Shopify before the picking was
        validated in Odoo. A picking for a part of it must neither split it (which Shopify refuses) nor ask
        for the preparation again.
        """
        prepared = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)], status='IN_PROGRESS')

        result, fulfill, prepared_calls, splits = self._send([prepared], lines=[(100, 2)])

        self.assertFalse(splits)
        self.assertFalse(prepared_calls)
        fulfill.assert_not_called()
        self.assertEqual(result, [], 'The picking marked nothing ready, so it reports nothing')

    def test_picking_covering_the_whole_prepared_pickup_fulfillment_order_asks_for_nothing(self):
        prepared = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)], status='IN_PROGRESS')

        result, fulfill, prepared_calls, splits = self._send([prepared], lines=[(100, 4)])

        self.assertFalse(splits)
        self.assertFalse(prepared_calls, 'Shopify is not asked to prepare what is already ready')
        fulfill.assert_not_called()

    def test_other_error_while_marking_ready_for_pickup_is_raised(self):
        pickup = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 4)])
        other_error = {'message': 'Invalid fulfillment order ID provided.', 'code': 'FULFILLMENT_ORDER_INVALID'}

        with self.assertRaises(ShopifyApiError):
            self._send([pickup], lines=[(100, 4)], prepare_errors=[other_error])

    def test_shipping_fulfillment_order_is_still_fulfilled(self):
        """Regression guard: only pickup changes, a shipped parcel is still fulfilled with its tracking."""
        shipping = _fulfillment_order(1, self.LOCATION, 'SHIPPING', [(100, 4)])

        result, fulfill, prepared, splits = self._send([shipping], lines=[(100, 4)])

        fulfill.assert_called_once()
        self.assertFalse(prepared)
        self.assertFalse(splits)
        self.assertEqual(result, [{'id': 'fulfillment'}])

    def test_pickup_point_fulfillment_order_is_fulfilled_with_its_tracking(self):
        """The parcel is sent to a pickup point, so it is not marked ready for pickup but fulfilled."""
        pickup_point = _fulfillment_order(1, self.LOCATION, 'PICKUP_POINT', [(100, 4)])

        result, fulfill, prepared, splits = self._send([pickup_point], lines=[(100, 4)])

        fulfill.assert_called_once()
        self.assertFalse(prepared)
        self.assertFalse(splits)
        self.assertEqual(result, [{'id': 'fulfillment'}])

    def test_order_with_shipping_and_pickup_fulfills_one_and_marks_the_other_ready(self):
        shipping = _fulfillment_order(1, self.LOCATION, 'SHIPPING', [(100, 2)])
        pickup = _fulfillment_order(2, self.LOCATION, 'PICK_UP', [(101, 3)])

        result, fulfill, prepared, splits = self._send([shipping, pickup], lines=[(100, 2), (101, 3)])

        fulfill.assert_called_once()
        self.assertEqual(fulfill.call_args.kwargs['lines_data'][0]['quantity'], 2)
        self.assertEqual(self._prepared_ids(prepared), ['gid://shopify/FulfillmentOrder/2'])
        self.assertFalse(splits)

    def test_backorder_marks_the_rest_ready_when_shopify_lists_the_ready_part_first(self):
        """The order Shopify lists fulfillment orders in is not documented, so it must not decide what is marked ready.

        The first picking marked two of four ready, so that part is `IN_PROGRESS` and the rest is still open. The
        backorder must mark the rest ready instead of being matched to the part that already is.
        """
        ready = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 2)], status='IN_PROGRESS')
        rest = _fulfillment_order(2, self.LOCATION, 'PICK_UP', [(100, 2)])

        result, fulfill, prepared, splits = self._send([ready, rest], lines=[(100, 2)])

        self.assertEqual(self._prepared_ids(prepared), ['gid://shopify/FulfillmentOrder/2'])
        self.assertFalse(splits)
        fulfill.assert_not_called()

    def test_backorder_marks_the_rest_ready_when_shopify_lists_it_first(self):
        rest = _fulfillment_order(2, self.LOCATION, 'PICK_UP', [(100, 2)])
        ready = _fulfillment_order(1, self.LOCATION, 'PICK_UP', [(100, 2)], status='IN_PROGRESS')

        result, fulfill, prepared, splits = self._send([rest, ready], lines=[(100, 2)])

        self.assertEqual(self._prepared_ids(prepared), ['gid://shopify/FulfillmentOrder/2'])
        self.assertFalse(splits)

    def test_order_with_shipping_and_pickup_reports_the_fulfillment_and_the_ready_order(self):
        shipping = _fulfillment_order(1, self.LOCATION, 'SHIPPING', [(100, 2)])
        pickup = _fulfillment_order(2, self.LOCATION, 'PICK_UP', [(101, 3)])

        result, fulfill, prepared, splits = self._send([shipping, pickup], lines=[(100, 2), (101, 3)])

        self.assertEqual(result, [{'id': 'fulfillment'}] + self._ready_report('2'))

    def test_fulfillment_reports_every_fulfillment_order_it_closed(self):
        """One fulfillment may take lines of several fulfillment orders; a collection is matched by all of them."""
        fulfillment = self.adapter.gql.Fulfillment.set(
            id='gid://shopify/Fulfillment/7',
            fulfillmentOrders=[
                {'id': 'gid://shopify/FulfillmentOrder/901'},
                {'id': 'gid://shopify/FulfillmentOrder/902'},
            ],
        )

        self.assertEqual([x.id_str for x in fulfillment.fulfillment_orders], ['901', '902'])
