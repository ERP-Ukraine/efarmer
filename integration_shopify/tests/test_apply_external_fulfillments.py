# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json

from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase
from .json_data import fulfillment_list_1, fulfillment_list_2


class TestIntegrationShopifyFulfillmentsCommon(IntegrationShopifyBase):

    @classmethod
    def setUpClass(cls):
        super(TestIntegrationShopifyFulfillmentsCommon, cls).setUpClass()

        cls.customer = cls.env['res.partner'].with_company(cls.company).create({
            'name': 'test-customer',
        })

        cls.wh_odoo1 = cls.env['stock.warehouse'].with_company(cls.company).create({
            'name': 'wh-odoo-1',
            'code': 'wh100',
            'company_id': cls.company.id,
        })
        cls.wh_odoo2 = cls.env['stock.warehouse'].with_company(cls.company).create({
            'name': 'wh-odoo-2',
            'code': 'wh200',
            'company_id': cls.company.id,
        })

        # First product
        vals_product_1 = {
            'name': 'table100',
            'is_storable': True,
            'default_code': 'default_code_table100',
            'integration_ids': [(6, 0, cls.integration.ids)],
        }
        product_1 = cls.env['product.template'].with_context(skip_product_export=True).create(vals_product_1)
        cls.prod1 = product_1.product_variant_ids

        cls.env['stock.quant'].create({
            'product_id': cls.prod1.id,
            'location_id': cls.wh_odoo1.lot_stock_id.id,
            'quantity': 500,
        })
        cls.env['stock.quant'].create({
            'product_id': cls.prod1.id,
            'location_id': cls.wh_odoo2.lot_stock_id.id,
            'quantity': 600,
        })

        # Second product
        vals_product_2 = {
            'name': 'table200',
            'is_storable': True,
            'default_code': 'default_code_table200',
            'integration_ids': [(6, 0, cls.integration.ids)],
        }
        product_2 = cls.env['product.template'].with_context(skip_product_export=True).create(vals_product_2)
        cls.prod2 = product_2.product_variant_ids

        cls.env['stock.quant'].create({
            'product_id': cls.prod2.id,
            'location_id': cls.wh_odoo1.lot_stock_id.id,
            'quantity': 700,
        })
        cls.env['stock.quant'].create({
            'product_id': cls.prod2.id,
            'location_id': cls.wh_odoo2.lot_stock_id.id,
            'quantity': 800,
        })


@tagged('post_install', '-at_install')
class TestIntegrationShopifyFulfillments(TestIntegrationShopifyFulfillmentsCommon):

    def _get_wh_from_external_location_patch(self, external_location):
        if external_location == 'external-location-1':
            return self.wh_odoo1
        if external_location == 'external-location-2':
            return self.wh_odoo2
        return False

    def _create_single_wh_order(self):
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.wh_odoo1.id,
            'integration_id': self.integration.id,
            'order_line': [
                (
                    0, 0, {
                        'product_id': self.prod1.id,
                        'product_uom_qty': 3,
                        'price_unit': 12,
                        'warehouse_id': self.wh_odoo1.id,
                        'integration_external_id': 'external-line-1.1',
                        'external_location_id': 'external-location-1',
                    },
                ),
                (
                    0, 0, {
                        'product_id': self.prod2.id,
                        'product_uom_qty': 2,
                        'price_unit': 15,
                        'warehouse_id': self.wh_odoo1.id,
                        'integration_external_id': 'external-line-1.2',
                        'external_location_id': 'external-location-1',
                    },
                ),
            ],
        })

        Fulfillment = self.env['external.order.fulfillment'].with_context(integration_id=self.integration.id)

        fulfillments = []
        for data in json.loads(fulfillment_list_1):
            record = Fulfillment._get_or_create_from_external(data)
            fulfillments.append((4, record.id, 0))

        order.external_fulfillment_ids = fulfillments
        return order

    def _create_multiple_wh_order(self):
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.wh_odoo1.id,
            'integration_id': self.integration.id,
            'order_line': [
                (
                    0, 0, {
                        'product_id': self.prod1.id,
                        'product_uom_qty': 2,
                        'price_unit': 15,
                        'warehouse_id': self.wh_odoo1.id,
                        'integration_external_id': 'external-line-1.1',
                        'external_location_id': 'external-location-1',
                    },
                ),
                (
                    0, 0, {
                        'product_id': self.prod2.id,
                        'product_uom_qty': 1,
                        'price_unit': 12,
                        'warehouse_id': self.wh_odoo1.id,
                        'integration_external_id': 'external-line-1.2',
                        'external_location_id': 'external-location-1',
                    },
                ),
                (
                    0, 0, {
                        'product_id': self.prod2.id,
                        'product_uom_qty': 1,
                        'price_unit': 12,
                        'warehouse_id': self.wh_odoo2.id,
                        'integration_external_id': 'external-line-1.2',
                        'external_location_id': 'external-location-2',
                    },
                ),
                (
                    0, 0, {
                        'product_id': self.prod1.id,
                        'product_uom_qty': 1,
                        'price_unit': 15,
                        'warehouse_id': self.wh_odoo2.id,
                        'integration_external_id': 'external-line-1.1',
                        'external_location_id': 'external-location-2',
                    },
                ),
            ],
        })

        Fulfillment = self.env['external.order.fulfillment'].with_context(integration_id=self.integration.id)

        fulfillments = []
        for data in json.loads(fulfillment_list_2):
            record = Fulfillment._get_or_create_from_external(data)
            fulfillments.append((4, record.id, 0))

        order.external_fulfillment_ids = fulfillments
        return order

    def test_init_checking(self):
        self.assertEqual(self.wh_odoo1.name, 'wh-odoo-1')
        self.assertEqual(self.wh_odoo2.name, 'wh-odoo-2')

        self.assertEqual(self.prod1.default_code, 'default_code_table100')
        self.assertEqual(self.prod2.default_code, 'default_code_table200')

    def test_single_external_wh_with_odoo_multisource(self):
        if not self.env['res.users'].is_module_installed('sale_sourced_by_line'):
            return self.assertTrue(1)

        # Add patch
        self.patch(
            type(self.integration),
            '_get_wh_from_external_location',
            self._get_wh_from_external_location_patch,
        )

        order = self._create_single_wh_order()
        self.assertTrue(len(order.external_fulfillment_ids), 3)

        # 1. Confirm order
        order.action_confirm()
        self.assertTrue(len(order.picking_ids), 1)
        self.assertTrue(order.is_available_multi_stock_for_so)  # Odoo multisource
        self.assertTrue(order.is_procurement_grouped)  # Odoo group pickings by source

        # 2. Apply fulfillments
        # 2.1 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[0]
        self.assertEqual(fulfillment.name, '#1124.1')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 2)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_ids.move_line_ids), 1)
        self.assertEqual(picking.move_ids.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids.move_line_ids.quantity), 1)

        # 2.2 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[1]
        self.assertEqual(fulfillment.name, '#1124.2')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_ids.move_line_ids), 1)
        self.assertEqual(picking.move_ids.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids.move_line_ids.quantity), 1)

        # 2.3 --> default_code_table200=2 + default_code_table100=1
        fulfillment = order.external_fulfillment_ids[2]
        self.assertEqual(fulfillment.name, '#1124.3')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_ids), 2)
        self.assertEqual(len(picking.move_ids[0].move_line_ids), 1)
        self.assertEqual(picking.move_ids[0].move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_ids[0].move_line_ids.quantity), 2)

        self.assertEqual(len(picking.move_ids[1].move_line_ids), 1)
        self.assertEqual(picking.move_ids[1].move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids[1].move_line_ids.quantity), 1)

        # All pickings are done
        self.assertTrue(all((x.state == 'done') for x in order.picking_ids))

    def test_multiple_external_wh_with_odoo_multisource(self):
        if not self.env['res.users'].is_module_installed('sale_sourced_by_line'):
            return self.assertTrue(1)

        # Add patch
        self.patch(
            type(self.integration),
            '_get_wh_from_external_location',
            self._get_wh_from_external_location_patch,
        )

        order = self._create_multiple_wh_order()
        self.assertTrue(len(order.external_fulfillment_ids), 4)

        # 1. Confirm order
        order.action_confirm()
        self.assertTrue(order.is_available_multi_stock_for_so)  # Odoo multisource
        self.assertTrue(order.is_procurement_grouped)  # Odoo group pickings by source
        self.assertTrue(len(order.picking_ids), 2)

        # 2. Apply fulfillments
        # 2.1 --> default_code_table100=1 + default_code_table200=1
        fulfillment = order.external_fulfillment_ids[0]
        self.assertEqual(fulfillment.name, '#1122.1')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_ids), 2)
        self.assertEqual(len(picking.move_ids[0].move_line_ids), 1)
        self.assertEqual(picking.move_ids[0].move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids[0].move_line_ids.quantity), 1)

        self.assertEqual(len(picking.move_ids[1].move_line_ids), 1)
        self.assertEqual(picking.move_ids[1].move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_ids[1].move_line_ids.quantity), 1)

        # 2.2 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[1]
        self.assertEqual(fulfillment.name, '#1122.2')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo2.id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_ids.move_line_ids), 1)
        self.assertEqual(picking.move_ids.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids.move_line_ids.quantity), 1)

        # 2.3 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[2]
        self.assertEqual(fulfillment.name, '#1122.3')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_ids.move_line_ids), 1)
        self.assertEqual(picking.move_ids.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_ids.move_line_ids.quantity), 1)

        # 2.4 --> default_code_table200=1
        fulfillment = order.external_fulfillment_ids[3]
        self.assertEqual(fulfillment.name, '#1122.4')

        _, pick_ids = fulfillment.validate()
        pick_id = pick_ids[0]

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo2.id)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(len(picking.move_ids.move_line_ids), 1)
        self.assertEqual(picking.move_ids.move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_ids.move_line_ids.quantity), 1)

        # All pickings are done
        self.assertTrue(all((x.state == 'done') for x in order.picking_ids))


@tagged('post_install', '-at_install', 'test_shopify_pickup_fulfillment')
class TestShopifyPickupCollectionImport(TestIntegrationShopifyFulfillmentsCommon):
    """A pickup picking only marks the goods ready in Shopify, so there is no fulfillment for them until the merchant
    records that the customer collected them. "Auto-Apply Fulfillments" brings that fulfillment back. It has to be
    matched, through the fulfillment order it closes, to the picking that marked those goods ready, not to a
    backorder of the rest that is still on the shelf.
    """

    LINE = 'external-line-1.1'

    def _order(self, qty=4):
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.wh_odoo1.id,
            'integration_id': self.integration.id,
            'order_line': [(0, 0, {
                'product_id': self.prod1.id,
                'product_uom_qty': qty,
                'price_unit': 12,
                'warehouse_id': self.wh_odoo1.id,
                'integration_external_id': self.LINE,
                'external_location_id': 'external-location-1',
            })],
        })
        order.action_confirm()

        return order

    def _deliver(self, order, qty, fulfillment_order_ids=''):
        """Validate `qty` pieces of the open picking, keep the rest as a backorder, and record the pickup
        fulfillment orders the export reported as marked ready for it.
        """
        picking = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True

        picking.with_context(
            skip_backorder=True,
            picking_ids_not_to_backorder=[],
            skip_sms=True,
            skip_dispatch_to_external=True,
        ).button_validate()
        self.assertEqual(picking.state, 'done')

        if fulfillment_order_ids:
            order._apply_values_from_external({'order_fulfillments': [{
                'picking_id': picking.id,
                'prepared_fulfillment_order_ids': fulfillment_order_ids.split(','),
            }]})

        return picking

    def _fulfillment(self, order, qty, external_id, fulfillment_orders=''):
        """`fulfillment_orders`: comma-separated ids of the Shopify fulfillment orders it closed."""
        record = self.env['external.order.fulfillment'].with_context(
            integration_id=self.integration.id,
        )._get_or_create_from_external({
            'name': '#1.%s' % external_id,
            'external_status': 'success',
            'external_str_id': external_id,
            'tracking_number': '',
            'tracking_company': '',
            'external_location_id': 'external-location-1',
            'shopify_fulfillment_orders': [x for x in fulfillment_orders.split(',') if x],
            'lines': [{
                'external_str_id': self.LINE,
                'quantity': qty,
                'external_reference': 'default_code_table100',
                'fulfillable_quantity': 0,
                'code': 'code-%s' % external_id,
            }],
        })
        order.external_fulfillment_ids = [(4, record.id)]

        return record

    @staticmethod
    def _open_pickings(order):
        return order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))

    def test_export_of_a_pickup_picking_keeps_its_fulfillment_orders(self):
        order = self._order()
        picking = self._deliver(order, 2, '901')
        order._apply_values_from_external({'order_fulfillments': [{
            'picking_id': picking.id,
            'prepared_fulfillment_order_ids': ['902', '901'],
        }]})

        self.assertEqual(picking.shopify_ready_fulfillment_orders, ['901', '902'])
        self.assertFalse(order.external_fulfillment_ids, 'The report is not a fulfillment')

    def test_collection_of_goods_odoo_marked_ready_leaves_the_backorder_alone(self):
        """Two of four were delivered and marked ready; the customer collected them."""
        order = self._order()
        first = self._deliver(order, 2, '901')
        backorder = self._open_pickings(order)

        collection = self._fulfillment(order, 2, '7001', '901')
        collection.validate()

        self.assertTrue(collection.is_done)
        self.assertEqual(collection.picking_id, first)
        self.assertEqual(backorder.state, 'assigned', 'The other two pieces are still on the shelf')
        self.assertEqual(order.order_line.qty_delivered, 2)

    def test_collections_are_linked_to_their_pickings_in_any_order(self):
        order = self._order()
        first = self._deliver(order, 2, '901')
        second = self._deliver(order, 2, '902')

        collection_2 = self._fulfillment(order, 2, '7002', '902')
        collection_2.validate()
        collection_1 = self._fulfillment(order, 2, '7001', '901')
        collection_1.validate()

        self.assertEqual(collection_1.picking_id, first)
        self.assertEqual(collection_2.picking_id, second)
        self.assertEqual(order.order_line.qty_delivered, 4)

    def test_collection_in_two_parts_of_one_ready_fulfillment_order(self):
        """The whole order was marked ready; the merchant recorded the collection in two steps."""
        order = self._order()
        picking = self._deliver(order, 4, '901')

        for external_id in ('7001', '7002'):
            collection = self._fulfillment(order, 2, external_id, '901')
            collection.validate()

            self.assertTrue(collection.is_done)
            self.assertEqual(collection.picking_id, picking)

        self.assertEqual(len(order.picking_ids), 1)

    def test_collection_of_two_ready_fulfillment_orders_is_linked(self):
        """One collection may close several fulfillment orders; both were marked ready by Odoo."""
        order = self._order()
        first = self._deliver(order, 2, '901')
        self._deliver(order, 2, '902')

        collection = self._fulfillment(order, 4, '7001', '902,901')
        collection.validate()

        self.assertTrue(collection.is_done)
        self.assertEqual(collection.picking_id, first)
        self.assertEqual(len(order.picking_ids), 2)

    def test_collection_of_a_ready_and_an_open_fulfillment_order_is_not_taken_as_the_pickings(self):
        """The customer took the ready part and the part still on the shelf in one collection.

        Fulfillment order 903 was never marked ready by Odoo, so its goods are not delivered there. The collection
        goes the usual way; it is bigger than the open delivery, so it fails visibly instead of being dropped.
        """
        order = self._order()
        first = self._deliver(order, 2, '901')
        backorder = self._open_pickings(order)

        collection = self._fulfillment(order, 4, '7001', '901,903')
        collection.validate()

        self.assertFalse(collection.is_done)
        self.assertFalse(collection.picking_id, 'Not linked to %s, which holds only a part of it' % first.name)
        self.assertEqual(backorder.state, 'assigned')

    def test_collection_before_any_delivery_validates_the_picking(self):
        """Regression guard: the merchant recorded a collection of goods Odoo had not marked ready."""
        order = self._order()
        picking = self._open_pickings(order)

        collection = self._fulfillment(order, 2, '7001', '901')
        collection.validate()

        self.assertTrue(collection.is_done)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(collection.picking_id, picking)
        self.assertEqual(order.order_line.qty_delivered, 2)

    def test_fulfillment_of_a_shipment_is_matched_to_a_pending_delivery_as_before(self):
        """Regression guard: only a picking that marked pickup goods ready is tied to a fulfillment.

        Odoo delivered two pieces by shipment but the export failed, and the merchant created a fulfillment in
        Shopify. Which two pieces it stands for is not known, so it validates the open delivery as it always did.
        """
        order = self._order()
        self._deliver(order, 2)
        backorder = self._open_pickings(order)

        fulfillment = self._fulfillment(order, 2, '7001', '555')
        fulfillment.validate()

        self.assertTrue(fulfillment.is_done)
        self.assertEqual(backorder.state, 'done')
        self.assertEqual(fulfillment.picking_id, backorder)
