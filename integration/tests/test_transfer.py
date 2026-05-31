# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from .config.integration_init import OdooIntegrationInit
from ..tools import PickingLine, PickingSerializer, SaleTransferSerializer


# PickingLine contain: (
#     external_line_id, qty_delivered (sale.order.line), quantity_done (stock.move), is_kit
# )

picking_lines1 = [
    ('external_id1', 5, 12 , True, True),
    ('external_id1', 4, 3 , False, True),
    ('external_id2', 3, 1 , False, True),
    ('external_id2', 3, 6 , True, True),
    ('external_id3', 6, 4 , False, True),
]

picking_lines2 = [
    ('external_id1', 5, 21 , True, True),
    ('external_id2', 3, 13 , True, True),
    ('external_id3', 6, 1 , False, True),
]

picking_lines3 = [
    ('external_id1', 5, 10 , True, True),
    ('external_id2', 3, 12 , True, True),
    ('external_id3', 6, 1 , False, True),
]

picking_lines4 = [
    ('external_id1', 5, 16 , True, True),
    ('external_id2', 3, 17 , True, True),
    ('external_id3', 6, 2 , False, True),
]

picking_lines5 = [
    ('external_id1', 5, 1, False, True),
]

data_list1 = [
    (
        {
            'erp_id': 104,
            'name': 'Picking1-standard',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref1',
            'is_backorder': False,
            'is_dropship': False,
        },
        picking_lines1,
    ),
    (
        {
            'erp_id': 105,
            'name': 'Picking2-backorder',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref2',
            'is_backorder': True,
            'is_dropship': False,
        },
        picking_lines2,
    ),
    (
        {
            'erp_id': 103,
            'name': 'Picking3-dropship',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref3',
            'is_backorder': False,
            'is_dropship': True,
        },
        picking_lines3,
    ),
]

data_list2 = [
    (
        {
            'erp_id': 104,
            'name': 'Picking1-standard',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref1',
            'is_backorder': False,
            'is_dropship': False,
        },
        picking_lines1,
    ),
    (
        {
            'erp_id': 105,
            'name': 'Picking2-backorder',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref2',
            'is_backorder': True,
            'is_dropship': False,
        },
        picking_lines4,
    ),
]

data_list3 = [
    (
        {
            'erp_id': 106,
            'name': 'Picking1-standard',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref1',
            'is_backorder': False,
            'is_dropship': False,
        },
        picking_lines4,
    ),
    (
        {
            'erp_id': 107,
            'name': 'Picking3-dropship',
            'carrier': 'Carrier',
            'carrier_code': 'Carrier',
            'tracking': 'tracking_ref3',
            'is_backorder': False,
            'is_dropship': True,
        },
        picking_lines5,
    ),
]


def to_export_format(data, lines):
    return PickingSerializer(data, [PickingLine(*x) for x in lines])


def to_export_format_multi(data_list):
    tracking_data_list = list()

    for (data, lines) in data_list:
        pdata = to_export_format(data, lines)
        tracking_data_list.append(pdata)

    return SaleTransferSerializer(tracking_data_list)


@tagged('post_install', '-at_install', 'test_integration_core')
class TestTransfer(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_standard_backorder_dropship(self):
        """
        Standard + backorder + dropship.
        Every picking has duplicated lines affected by the `kits` and have to be skipped.

        [
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id1",
                        "qty": 5
                    },
                    {
                        "id": "external_id2",
                        "qty": 3
                    },
                    {
                        "id": "external_id3",
                        "qty": 4
                    }
                ],
                "name": "Picking1-standard",
                "tracking": "tracking_ref1"
            },
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id3",
                        "qty": 1
                    }
                ],
                "name": "Picking2-backorder",
                "tracking": "tracking_ref2"
            },
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id3",
                        "qty": 1
                    }
                ],
                "name": "Picking3-dropship",
                "tracking": "tracking_ref3"
            }
        ]
        """

        transfer = to_export_format_multi(data_list1)
        transfer.squash()
        data_list = transfer.dump()

        self.assertEqual(len(data_list), 3)

        data1, data2, data3 = data_list

        # 1.
        self.assertEqual(data1['carrier_code'], 'Carrier')
        self.assertEqual(data1['name'], 'Picking1-standard')
        self.assertEqual(data1['tracking'], 'tracking_ref1')
        self.assertEqual(len(data1['lines']), 3)

        line1, line2, line3 = data1['lines']

        self.assertEqual(line1['id'], 'external_id1')
        self.assertEqual(line1['qty'], 5)

        self.assertEqual(line2['id'], 'external_id2')
        self.assertEqual(line2['qty'], 3)

        self.assertEqual(line3['qty'], 4)
        self.assertEqual(line3['id'], 'external_id3')

        # 2.
        self.assertEqual(data2['carrier_code'], 'Carrier')
        self.assertEqual(data2['name'], 'Picking2-backorder')
        self.assertEqual(data2['tracking'], 'tracking_ref2')
        self.assertEqual(len(data2['lines']), 1)

        line1 = data2['lines'][0]

        self.assertEqual(line1['id'], 'external_id3')
        self.assertEqual(line1['qty'], 1)

        # 3.
        self.assertEqual(data3['carrier_code'], 'Carrier')
        self.assertEqual(data3['name'], 'Picking3-dropship')
        self.assertEqual(data3['tracking'], 'tracking_ref3')
        self.assertEqual(len(data3['lines']), 1)

        line1 = data3['lines'][0]

        self.assertEqual(line1['id'], 'external_id3')
        self.assertEqual(line1['qty'], 1)

    def test_standard_backorder(self):
        """
        Standard + backorder.
        Every picking has duplicated lines affected by the `kits` and have to be skipped.

        [
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id1",
                        "qty": 5
                    },
                    {
                        "id": "external_id2",
                        "qty": 3
                    },
                    {
                        "id": "external_id3",
                        "qty": 4
                    }
                ],
                "name": "Picking1-standard",
                "tracking": "tracking_ref1"
            },
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id3",
                        "qty": 2
                    }
                ],
                "name": "Picking2-backorder",
                "tracking": "tracking_ref2"
            }
        ]
        """

        transfer = to_export_format_multi(data_list2)
        transfer.squash()
        data_list = transfer.dump()

        self.assertEqual(len(data_list), 2)

        data1, data2 = data_list

        # 1.
        self.assertEqual(data1['carrier_code'], 'Carrier')
        self.assertEqual(data1['name'], 'Picking1-standard')
        self.assertEqual(data1['tracking'], 'tracking_ref1')
        self.assertEqual(len(data1['lines']), 3)

        line1, line2, line3 = data1['lines']

        self.assertEqual(line1['id'], 'external_id1')
        self.assertEqual(line1['qty'], 5)

        self.assertEqual(line2['id'], 'external_id2')
        self.assertEqual(line2['qty'], 3)

        self.assertEqual(line3['qty'], 4)
        self.assertEqual(line3['id'], 'external_id3')

        # 2.
        self.assertEqual(data2['carrier_code'], 'Carrier')
        self.assertEqual(data2['name'], 'Picking2-backorder')
        self.assertEqual(data2['tracking'], 'tracking_ref2')
        self.assertEqual(len(data2['lines']), 1)

        line1 = data2['lines'][0]

        self.assertEqual(line1['id'], 'external_id3')
        self.assertEqual(line1['qty'], 2)

    def test_standard_dropship(self):
        """
        Standart + dropship.
        Standart picking has done lines because of kits. Dropship contains not done line
        with the same external_id as in standard, so his tracking wil be reassigned.

        [
            {
                "carrier": "Carrier",
                "lines": [
                    {
                        "id": "external_id1",
                        "qty": 5
                    },
                    {
                        "id": "external_id2",
                        "qty": 3
                    },
                    {
                        "id": "external_id3",
                        "qty": 2
                    }
                ],
                "name": "Picking1-standard",
                "tracking": "tracking_ref1, tracking_ref3"
            }
        ]
        """

        transfer = to_export_format_multi(data_list3)
        transfer.squash()
        data_list = transfer.dump()

        self.assertEqual(len(data_list), 1)

        data1 = data_list[0]

        # 1.
        self.assertEqual(data1['carrier_code'], 'Carrier')
        self.assertEqual(data1['name'], 'Picking1-standard')
        self.assertEqual(data1['tracking'], 'tracking_ref1, tracking_ref3')  # Joint tracking
        self.assertEqual(len(data1['lines']), 3)

        line1, line2, line3 = data1['lines']

        self.assertEqual(line1['id'], 'external_id1')
        self.assertEqual(line1['qty'], 5)

        self.assertEqual(line2['id'], 'external_id2')
        self.assertEqual(line2['qty'], 3)

        self.assertEqual(line3['qty'], 2)
        self.assertEqual(line3['id'], 'external_id3')


@tagged('post_install', '-at_install', 'test_integration_core')
class TestPickingExportFormat(OdooIntegrationInit):
    """Regression tests for `stock.picking._to_export_format` (RDSE-102).

    When an order contains a kit (phantom BoM) line alongside regular lines,
    the kit's external line was reported with a stale `qty_demand` borrowed
    from the last move processed in the aggregation loop, so Shopify saw the
    kit as under-fulfilled.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Cache the kit fixture across tests — it does not depend on any
        # per-test records, so it is safe to create once at class level.
        cls.component = cls.env['product.product'].create({
            'name': 'Kit Component',
            'type': 'consu',
            'is_storable': True,
        })
        cls.kit_product = cls.env['product.product'].create({
            'name': 'Kit Parent',
            'type': 'consu',
            'is_storable': True,
            'default_code': 'KIT_RDSE102',
        })
        # Phantom BoM: 1 kit = 2 components.
        cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.kit_product.product_tmpl_id.id,
            'type': 'phantom',
            'product_qty': 1,
            'bom_line_ids': [
                (0, 0, {'product_id': cls.component.id, 'product_qty': 2}),
            ],
        })

    def setUp(self):
        super().setUp()

        self.warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id_1.id)], limit=1,
        )
        self.stock_location = self.warehouse.lot_stock_id
        self.partner = self.env.ref('integration.test_main_partner')

        # External mapping for the kit; product_pp_1 / product_pp_2 are already
        # mapped via OdooIntegrationInit. Must be in setUp because
        # integration_no_api_1 is re-created per test.
        kit_external = self._create_external(
            self.kit_product, self.integration_no_api_1, 'EXT_KIT_RDSE102',
        )
        self._create_mapping(
            self.kit_product, kit_external, self.integration_no_api_1,
        )

        # Stock so the picking can be validated.
        for product in (self.component, self.product_pp_1, self.product_pp_2):
            self.env['stock.quant']._update_available_quantity(
                product, self.stock_location, 100,
            )

    def _create_order(self, line_specs):
        """`line_specs`: list of (product, qty, integration_external_id)."""
        return self.env['sale.order'].with_company(self.company_id_1).create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse.id,
            'integration_id': self.integration_no_api_1.id,
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'price_unit': 10,
                    'integration_external_id': ext_id,
                })
                for product, qty, ext_id in line_specs
            ],
        })

    def _confirm_and_validate(self, order):
        order.action_confirm()
        self.assertEqual(len(order.picking_ids), 1)
        picking = order.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        return picking

    def test_kit_reports_parent_qty_when_followed_by_regular_lines(self):
        """Kit first, regular lines after.

        Pre-fix this returned qty=1 for 'ext-kit' (the qty_demand leaking from
        the last regular line) instead of qty=2.
        """
        order = self._create_order([
            (self.kit_product, 2, 'ext-kit'),
            (self.product_pp_1, 1, 'ext-p1'),
            (self.product_pp_2, 1, 'ext-p2'),
        ])
        picking = self._confirm_and_validate(order)

        serializer = picking._to_export_format(
            self.integration_no_api_1, multi_serialization=True,
        )
        qty_by_ext = {
            line.external_id: line.get_qty() for line in serializer.approved_lines
        }

        self.assertEqual(qty_by_ext['ext-kit'], 2)
        self.assertEqual(qty_by_ext['ext-p1'], 1)
        self.assertEqual(qty_by_ext['ext-p2'], 1)

    def test_kit_reports_parent_qty_regardless_of_line_order(self):
        """Same assertion, kit line created last so it is also processed last
        in the move loop; the fix must hold either way.
        """
        order = self._create_order([
            (self.product_pp_1, 1, 'ext-p1'),
            (self.product_pp_2, 1, 'ext-p2'),
            (self.kit_product, 2, 'ext-kit'),
        ])
        picking = self._confirm_and_validate(order)

        serializer = picking._to_export_format(
            self.integration_no_api_1, multi_serialization=True,
        )
        qty_by_ext = {
            line.external_id: line.get_qty() for line in serializer.approved_lines
        }

        self.assertEqual(qty_by_ext['ext-kit'], 2)
        self.assertEqual(qty_by_ext['ext-p1'], 1)
        self.assertEqual(qty_by_ext['ext-p2'], 1)
