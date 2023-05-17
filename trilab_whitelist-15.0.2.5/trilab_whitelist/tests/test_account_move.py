from odoo.tests import TransactionCase, tagged


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
            {'acc_number': 'PL05 1140 2004 0000 3002 7781 8070', 'partner_id': cls.partner_4.id}
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

    def test__x_wl_validate_bank_account_1(self):
        self.assertEqual(
            self.invoice_1._x_wl_validate_bank_account()[self.invoice_1.id]['error_type'],
            'positive',
            "Incorrect API response - should be positive because partner info is valid.",
        )

    def test__x_wl_validate_bank_account_2(self):
        self.assertEqual(
            self.invoice_2._x_wl_validate_bank_account()[self.invoice_2.id]['error_type'],
            'invalid_vat',
            "Incorrect message - this invoice has no partner selected.",
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
            "Incorrect message - partner of this invoice has invalid bank account number.",
        )

    def test__x_wl_validate_bank_account_5(self):
        self.assertEqual(
            self.invoice_5._x_wl_validate_bank_account()[self.invoice_5.id]['error_type'],
            'negative',
            "Incorrect API response - should be negative because partner info is invalid.",
        )
