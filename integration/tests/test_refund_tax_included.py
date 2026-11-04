# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_refund_tax_included')
class TestRefundTaxIncluded(ReturnsRefundsAccountingTestBase):
    """The credit note must match the refund for both tax modes of the Odoo tax (price included
    and price excluded), with the refund data in the shape each platform sends it:

    - net shape (WooCommerce, Shopify store with taxes excluded): the line price and subtotal
      are tax-EXCLUDED and the tax is a separate amount, so the gross refund is subtotal + tax;
    - gross shape (Shopify store with taxes included): the line price and subtotal already
      INCLUDE the tax, ``total_tax`` is the part of them that is tax.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration = cls._create_test_integration('Refund Tax Mode Test Integration')

        # The payments of this class must reach the invoice whatever the database's own bank
        # journals are set up with, so it carries a journal with an outstanding account of its own
        outstanding_account = cls.env['account.account'].with_company(cls.company).create({
            'name': 'Refund Tax Test Outstanding',
            'code': 'RTXOUT',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.bank_journal = cls.env['account.journal'].with_company(cls.company).create({
            'name': 'Refund Tax Test Bank',
            'type': 'bank',
            'code': 'RTXBK',
            'company_id': cls.company.id,
        })
        (
            cls.bank_journal.inbound_payment_method_line_ids
            | cls.bank_journal.outbound_payment_method_line_ids
        ).write({'payment_account_id': outstanding_account.id})

        cls.tax_excluded = cls.env['account.tax'].with_company(cls.company).create({
            'name': 'VAT 15 excluded',
            'amount': 15.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_excluded',
        })
        cls.tax_included = cls.env['account.tax'].with_company(cls.company).create({
            'name': 'VAT 23 included',
            'amount': 23.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })

        # Payment method mapped to the bank journal: the refund journal is read from it
        external_payment_method = cls.env['integration.sale.order.payment.method.external'].create({
            'integration_id': cls.integration.id,
            'code': 'test-pm',
            'name': 'Test Payment Method',
            'payment_journal_id': cls.bank_journal.id,
        })
        cls.payment_method = cls.env['sale.order.payment.method'].create({'name': 'Test Payment Method'})
        cls.env['integration.sale.order.payment.method.mapping'].create({
            'integration_id': cls.integration.id,
            'external_payment_method_id': external_payment_method.id,
            'payment_method_id': cls.payment_method.id,
        })

        cls.discount_product = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Test Discount',
            'type': 'service',
            'taxes_id': [(5, 0, 0)],
        })
        cls.integration.discount_product_id = cls.discount_product.id

    def _create_paid_order(self, tax, quantity, gross_unit_price):
        """Confirmed order with one taxed line, a posted and paid invoice.

        ``gross_unit_price`` is the unit price as Odoo stores it for the tax mode: the price
        with tax for a price-included tax, the price without tax otherwise.
        """
        product = self.env['product.product'].with_company(self.company).create({
            'name': 'Taxed Product',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': gross_unit_price,
            'taxes_id': [(6, 0, tax.ids)],
        })
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
                'price_unit': gross_unit_price,
                'tax_ids': [(6, 0, tax.ids)],
                'integration_external_id': 'ext-line-1',
            })],
        })
        order.action_confirm()
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        self.env['account.payment.register'].with_context(
            active_ids=invoice.ids, active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})._create_payments()

        return order

    def _process_refund(self, order, quantity, unit_price, subtotal, total_tax, total):
        refund = self.env['external.order.refund'].create({
            'external_str_id': 'refund-%s' % order.id,
            'erp_order_id': order.id,
            'total_refunded_amount': total,
            'currency_id': order.currency_id.id,
            'note': 'Test refund',
            'created_at_external': '2026-04-30 12:00:00',
        })
        self.env['external.order.refund.line'].create({
            'refund_id': refund.id,
            'external_line_str_id': 'ext-line-1',
            'quantity': quantity,
            'restock_type': 'no_restock',
            'original_unit_price': unit_price,
            'subtotal': subtotal,
            'total_tax': total_tax,
            'currency_id': order.currency_id.id,
        })
        refund._process()

        return refund.credit_note_id

    def _assert_credit_note_matches(self, credit_note, total, tax):
        # No adjustment product is configured: a line that needs one would fail the refund (E555)
        self.assertAlmostEqual(credit_note.amount_total, total, places=2)
        self.assertAlmostEqual(credit_note.amount_tax, tax, places=2)
        self.assertAlmostEqual(credit_note.amount_residual, 0.0, places=2)
        self.assertFalse(
            credit_note.invoice_line_ids.filtered(lambda line: line.name == 'Refund adjustment'),
            'The credit note must not need an adjustment line',
        )

    # --- Price-included Odoo tax ---

    def test_included_tax_with_net_refund_data(self):
        """WooCommerce / Shopify taxes-excluded shape: 2 of 3 units, 100.00 net + 23.00 tax each."""
        order = self._create_paid_order(self.tax_included, quantity=3, gross_unit_price=123.0)

        credit_note = self._process_refund(
            order, quantity=2, unit_price=100.0, subtotal=200.0, total_tax=46.0, total=246.0,
        )

        self._assert_credit_note_matches(credit_note, total=246.0, tax=46.0)

    def test_included_tax_with_gross_refund_data(self):
        """Shopify taxes-included shape: 2 of 3 units, 123.00 gross each, 46.00 of it is tax."""
        order = self._create_paid_order(self.tax_included, quantity=3, gross_unit_price=123.0)

        credit_note = self._process_refund(
            order, quantity=2, unit_price=123.0, subtotal=246.0, total_tax=46.0, total=246.0,
        )

        self._assert_credit_note_matches(credit_note, total=246.0, tax=46.0)

    def test_included_tax_with_net_refund_data_and_discount(self):
        """Net shape with a line discount: 100.00 net unit price, 80.00 net after the discount."""
        order = self._create_paid_order(self.tax_included, quantity=1, gross_unit_price=123.0)

        credit_note = self._process_refund(
            order, quantity=1, unit_price=100.0, subtotal=80.0, total_tax=18.4, total=98.4,
        )

        self._assert_credit_note_matches(credit_note, total=98.4, tax=18.4)

    def test_included_tax_with_gross_refund_data_and_discount(self):
        """Gross shape with a line discount: 123.00 gross unit price, 98.40 gross after the discount."""
        order = self._create_paid_order(self.tax_included, quantity=1, gross_unit_price=123.0)

        credit_note = self._process_refund(
            order, quantity=1, unit_price=123.0, subtotal=98.4, total_tax=18.4, total=98.4,
        )

        self._assert_credit_note_matches(credit_note, total=98.4, tax=18.4)

    def test_included_tax_with_refund_data_without_tax_amount(self):
        """A line that carries no tax amount cannot be told apart from a gross one: its price is kept."""
        order = self._create_paid_order(self.tax_included, quantity=1, gross_unit_price=123.0)

        credit_note = self._process_refund(
            order, quantity=1, unit_price=123.0, subtotal=123.0, total_tax=0.0, total=123.0,
        )

        self.assertAlmostEqual(credit_note.invoice_line_ids.filtered('product_id').price_unit, 123.0, places=2)
        self.assertAlmostEqual(credit_note.amount_total, 123.0, places=2)
        self.assertAlmostEqual(credit_note.amount_residual, 0.0, places=2)

    # --- Price-excluded Odoo tax ---

    def test_excluded_tax_with_net_refund_data(self):
        """WooCommerce / Shopify taxes-excluded shape: 2 of 3 units, 100.00 net + 15.00 tax each."""
        order = self._create_paid_order(self.tax_excluded, quantity=3, gross_unit_price=100.0)

        credit_note = self._process_refund(
            order, quantity=2, unit_price=100.0, subtotal=200.0, total_tax=30.0, total=230.0,
        )

        self._assert_credit_note_matches(credit_note, total=230.0, tax=30.0)

    def test_excluded_tax_with_net_refund_data_and_discount(self):
        """Net shape with a line discount: 100.00 unit price, 80.00 after the discount."""
        order = self._create_paid_order(self.tax_excluded, quantity=1, gross_unit_price=100.0)

        credit_note = self._process_refund(
            order, quantity=1, unit_price=100.0, subtotal=80.0, total_tax=12.0, total=92.0,
        )

        self._assert_credit_note_matches(credit_note, total=92.0, tax=12.0)
