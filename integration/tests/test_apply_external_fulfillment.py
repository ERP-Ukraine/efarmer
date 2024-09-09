# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import pytest

from .config.integration_init import OdooIntegrationInit
from .json_data import fulfillment_list_1, fulfillment_list_2


class TestApplyExternalFulfillment(OdooIntegrationInit):

    def setUp(self):
        super(TestApplyExternalFulfillment, self).setUp()

        self.customer = self.env['res.partner'].with_company(self.company_id_1).create({
            'name': 'test-customer',
        })

        self.wh_odoo1 = self.env['stock.warehouse'].with_company(self.company_id_1).create({
            'name': 'wh-odoo-1',
            'code': 'wh100',
            'company_id': self.company_id_1.id,
        })
        self.wh_odoo2 = self.env['stock.warehouse'].with_company(self.company_id_1).create({
            'name': 'wh-odoo-2',
            'code': 'wh200',
            'company_id': self.company_id_1.id,
        })

        # First product
        vals_product_1 = self.generate_product_data(
            name='table100',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'].create(vals_product_1)
        self.prod1 = product_1.product_variant_ids

        self.env['stock.quant'].create({
            'product_id': self.prod1.id,
            'location_id': self.wh_odoo1.lot_stock_id.id,
            'quantity': 500,
        })
        self.env['stock.quant'].create({
            'product_id': self.prod1.id,
            'location_id': self.wh_odoo2.lot_stock_id.id,
            'quantity': 600,
        })

        # Second product
        vals_product_2 = self.generate_product_data(
            name='table200',
            integration=self.integration_no_api_1,
        )
        product_2 = self.env['product.template'].create(vals_product_2)
        self.prod2 = product_2.product_variant_ids

        self.env['stock.quant'].create({
            'product_id': self.prod2.id,
            'location_id': self.wh_odoo1.lot_stock_id.id,
            'quantity': 700,
        })
        self.env['stock.quant'].create({
            'product_id': self.prod2.id,
            'location_id': self.wh_odoo2.lot_stock_id.id,
            'quantity': 800,
        })

    def _create_single_wh_order(self):
        order = self.env['sale.order'].with_company(self.company_id_1).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.wh_odoo1.id,
            'integration_id': self.integration_no_api_1.id,
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

        Fulfillment = self.env['external.order.fulfillment'].with_context(erp_order_id=order.id)

        fulfillments = []
        for data in json.loads(fulfillment_list_1):
            record = Fulfillment._get_or_create_from_external(data)
            fulfillments.append((4, record.id, 0))

        order.external_fulfillment_ids = fulfillments
        return order

    def _create_myltiple_wh_order(self):
        order = self.env['sale.order'].with_company(self.company_id_1).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.wh_odoo1.id,
            'integration_id': self.integration_no_api_1.id,
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

        Fulfillment = self.env['external.order.fulfillment'].with_context(erp_order_id=order.id)

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

    @pytest.mark.skip(reason='OCA "sale_sourced_by_line" module is required')
    def test_single_external_wh_with_odoo_multisource(self):
        order = self._create_single_wh_order()
        self.assertTrue(len(order.external_fulfillment_ids), 3)

        # 1. Confirm order
        order.action_confirm()
        self.assertTrue(len(order.picking_ids), 1)
        self.assertTrue(order.is_available_multi_stock_for_so)  # Odoo multisource
        self.assertTrue(order.is_procurement_grouped)  # Odoo group pickings by source

        # 2. Apply fulfillments

        # Add patch
        def _get_wh_from_external_location_patch(self_, external_location):
            if external_location == 'external-line-1.1':
                return self.wh_odoo1
            if external_location == 'external-line-1.2':
                return self.wh_odoo2
            return False

        self.integration_no_api_1\
            ._patch_method(
                '_get_wh_from_external_location',
                _get_wh_from_external_location_patch,
            )

        # 2.1 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[0]
        self.assertEqual(fulfillment.name, '#1124.1')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 2)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(len(picking.move_lines.move_line_ids), 1)
        self.assertEqual(picking.move_lines.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines.move_line_ids.qty_done), 1)

        # 2.2 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[1]
        self.assertEqual(fulfillment.name, '#1124.2')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(len(picking.move_lines.move_line_ids), 1)
        self.assertEqual(picking.move_lines.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines.move_line_ids.qty_done), 1)

        # 2.3 --> default_code_table200=2 + default_code_table100=1
        fulfillment = order.external_fulfillment_ids[2]
        self.assertEqual(fulfillment.name, '#1124.3')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_lines), 2)
        self.assertEqual(len(picking.move_lines[0].move_line_ids), 1)
        self.assertEqual(picking.move_lines[0].move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_lines[0].move_line_ids.qty_done), 2)

        self.assertEqual(len(picking.move_lines[1].move_line_ids), 1)
        self.assertEqual(picking.move_lines[1].move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines[1].move_line_ids.qty_done), 1)

        # All pickings are done
        self.assertTrue(all((x.state == 'done') for x in order.picking_ids))

    @pytest.mark.skip(reason='OCA "sale_sourced_by_line" module is required')
    def test_multiple_external_wh_with_odoo_multisource(self):
        order = self._create_myltiple_wh_order()
        self.assertTrue(len(order.external_fulfillment_ids), 4)

        # 1. Confirm order
        order.action_confirm()
        self.assertTrue(order.is_available_multi_stock_for_so)  # Odoo multisource
        self.assertTrue(order.is_procurement_grouped)  # Odoo group pickings by source
        self.assertTrue(len(order.picking_ids), 2)

        # 2. Apply fulfillments

        # Add patch
        def _get_wh_from_external_location_patch(self_, external_location):
            if external_location == 'external-line-1.1':
                return self.wh_odoo1
            if external_location == 'external-line-1.2':
                return self.wh_odoo2
            return False

        self.integration_no_api_1\
            ._patch_method(
                '_get_wh_from_external_location',
                _get_wh_from_external_location_patch,
            )

        # 2.1 --> default_code_table100=1 + default_code_table200=1
        fulfillment = order.external_fulfillment_ids[0]
        self.assertEqual(fulfillment.name, '#1122.1')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 3)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_lines), 2)
        self.assertEqual(len(picking.move_lines[0].move_line_ids), 1)
        self.assertEqual(picking.move_lines[0].move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines[0].move_line_ids.qty_done), 1)

        self.assertEqual(len(picking.move_lines[1].move_line_ids), 1)
        self.assertEqual(picking.move_lines[1].move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_lines[1].move_line_ids.qty_done), 1)

        # 2.2 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[1]
        self.assertEqual(fulfillment.name, '#1122.2')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo2.id)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(len(picking.move_lines.move_line_ids), 1)
        self.assertEqual(picking.move_lines.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines.move_line_ids.qty_done), 1)

        # 2.3 --> default_code_table100=1
        fulfillment = order.external_fulfillment_ids[2]
        self.assertEqual(fulfillment.name, '#1122.3')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo1.id)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(len(picking.move_lines.move_line_ids), 1)
        self.assertEqual(picking.move_lines.move_line_ids.product_id.default_code, 'default_code_table100')
        self.assertEqual(int(picking.move_lines.move_line_ids.qty_done), 1)

        # 2.4 --> default_code_table200=1
        fulfillment = order.external_fulfillment_ids[3]
        self.assertEqual(fulfillment.name, '#1122.4')

        _, pick_id = fulfillment.validate()
        self.assertTrue(fulfillment.is_done)
        self.assertEqual(len(order.picking_ids), 4)

        picking = order.picking_ids.filtered(lambda x: x.id == pick_id)
        self.assertTrue(picking.state == 'done')
        self.assertEqual(picking.location_id.warehouse_id.id , self.wh_odoo2.id)
        self.assertEqual(len(picking.move_lines), 1)
        self.assertEqual(len(picking.move_lines.move_line_ids), 1)
        self.assertEqual(picking.move_lines.move_line_ids.product_id.default_code, 'default_code_table200')
        self.assertEqual(int(picking.move_lines.move_line_ids.qty_done), 1)

        # All pickings are done
        self.assertTrue(all((x.state == 'done') for x in order.picking_ids))
