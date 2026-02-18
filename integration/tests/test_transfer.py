# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

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
