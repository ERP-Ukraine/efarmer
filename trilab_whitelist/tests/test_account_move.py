from unittest import mock
from urllib.parse import urlparse

from odoo.tests import TransactionCase, tagged

_mocked_mapping = {
    '05114020040000300277818070': 'TAK',
    '61109010140000071219812874': 'NIE',
}


class MockedResponse:
    def __init__(self, json_data, status_code=200):
        self.status_code = status_code
        self.json_data = json_data
        self.reason = None
        self.ok = True if status_code == 200 else False
        self.reason = None

    def json(self):
        return self.json_data


def _mocked_requests_get(*args, **kwargs):
    path = urlparse(args[0]).path
    bank_account = path.split('/')[-1]
    data = {
        'result': {
            'requestId': 1,
            'accountAssigned': _mocked_mapping.get(bank_account, 'NIE'),
        }
    }
    return MockedResponse(data)


@tagged('trilab_whitelist')
class TestAccountMove(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestAccountMove, cls).setUpClass()

        cls.partner_1 = cls.env['res.partner'].create({'name': 'myOdoo', 'vat': 'PL8513156941'})

        cls.partner_2 = cls.env['res.partner'].create({'name': 'Some Company'})

        cls.partner_3 = cls.env['res.partner'].create({'name': 'Third Company', 'vat': 'PL9525144909'})

        cls.partner_4 = cls.env['res.partner'].create({'name': 'Trilab', 'vat': 'PL5342584136'})

        cls.partner_bank_1 = cls.env['res.partner.bank'].create(
            {'acc_number': 'PL05 1140 2004 0000 3002 7781 8070', 'partner_id': cls.partner_1.id}
        )

        cls.partner_bank_2 = cls.env['res.partner.bank'].create(
            {'acc_number': 'PL53 9453 0009 0079 4645 3654 538', 'partner_id': cls.partner_3.id}
        )

        cls.partner_bank_3 = cls.env['res.partner.bank'].create(
            {'acc_number': 'PL61 1090 1014 0000 0712 1981 2874', 'partner_id': cls.partner_4.id}
        )

        cls.invoice_1 = cls.env['account.move'].create(
            {'name': 'INV/2022/0001', 'partner_id': cls.partner_1.id, 'partner_bank_id': cls.partner_bank_1.id}
        )

        cls.invoice_2 = cls.env['account.move'].create({'name': 'INV/2022/0002'})

        cls.invoice_3 = cls.env['account.move'].create({'name': 'INV/2022/0003', 'partner_id': cls.partner_2.id})

        cls.invoice_4 = cls.env['account.move'].create(
            {'name': 'INV/2022/0004', 'partner_id': cls.partner_3.id, 'partner_bank_id': cls.partner_bank_2.id}
        )

        cls.invoice_5 = cls.env['account.move'].create(
            {'name': 'INV/2022/0005', 'partner_id': cls.partner_4.id, 'partner_bank_id': cls.partner_bank_3.id}
        )

    @mock.patch('requests.get', side_effect=_mocked_requests_get)
    def test__x_wl_validate_bank_account_1(self, mock_get):
        self.assertEqual(
            self.invoice_1._x_wl_validate_bank_account()[self.invoice_1.id]['error_type'],
            'positive',
            'Incorrect API response - should be positive because partner info is valid.',
        )

    def test__x_wl_validate_bank_account_2(self):
        self.assertEqual(
            self.invoice_2._x_wl_validate_bank_account()[self.invoice_2.id]['error_type'],
            'invalid_vat',
            'Incorrect message - this invoice has no partner selected.',
        )

    def test__x_wl_validate_bank_account_3(self):
        self.assertEqual(
            self.invoice_3._x_wl_validate_bank_account()[self.invoice_3.id]['error_type'],
            'invalid_vat',
            "Incorrect message - partner of this invoice doesn't have any VAT number.",
        )

    def test__x_wl_validate_bank_account_4(self):
        self.assertEqual(
            self.invoice_4._x_wl_validate_bank_account()[self.invoice_4.id]['error_type'],
            'invalid_bank_acc',
            'Incorrect message - partner of this invoice has invalid bank account number.',
        )

    @mock.patch('odoo.addons.trilab_whitelist.models.account_move.requests.get', side_effect=_mocked_requests_get)
    def test__x_wl_validate_bank_account_5(self, mock_get):
        self.assertEqual(
            self.invoice_5._x_wl_validate_bank_account()[self.invoice_5.id]['error_type'],
            'negative',
            'Incorrect API response - should be negative because partner info is invalid.',
        )
