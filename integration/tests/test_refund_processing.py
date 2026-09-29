# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..exceptions import PrerequisiteNotMet
from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_refund_processing')
class TestRefundProcessing(ReturnsRefundsAccountingTestBase):
    """Tests for external.order.refund._process() — credit note creation,
    refund payment registration, and fail-loud error guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration = cls._create_test_integration(
            'Refund Processing Test Integration',
        )

        cls.currency_eur = cls.env.ref('base.EUR')
        cls.currency_eur.active = True

        cls.product = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Test T-Shirt',
            'default_code': 'TSHIRT-P2-001',
            'type': 'consu',
            'list_price': 19.84,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })

        # A second product for mismatch tests
        cls.product_b = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Test Hat',
            'default_code': 'HAT-P2-001',
            'type': 'consu',
            'list_price': 25.00,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })

        # Discount product on the integration — required for refunds that
        # carry a discount line; resolved lazily by _adjust_credit_note_lines.
        cls.discount_product = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Test Discount',
            'default_code': 'TEST_REFUND_DISCOUNT',
            'type': 'service',
            'taxes_id': [(5, 0, 0)],
        })
        cls.integration.discount_product_id = cls.discount_product.id

        # Payment method mapped to the bank journal. Required because
        # _get_refund_journal() reads the journal from the order's payment
        # method (via its integration-side mapping) — there is no fallback
        # on the integration level.
        cls.external_payment_method = cls.env[
            'integration.sale.order.payment.method.external'
        ].create({
            'integration_id': cls.integration.id,
            'code': 'test-pm',
            'name': 'Test Payment Method',
            'payment_journal_id': cls.bank_journal.id,
        })
        cls.payment_method = cls.env['sale.order.payment.method'].create({
            'name': 'Test Payment Method',
        })
        cls.env['integration.sale.order.payment.method.mapping'].create({
            'integration_id': cls.integration.id,
            'external_payment_method_id': cls.external_payment_method.id,
            'payment_method_id': cls.payment_method.id,
        })

    def _create_confirmed_order_with_invoice(
        self, product=None, qty=1, price_unit=19.84,
        post_invoice=True, pay_invoice=True,
    ):
        """Helper: create a confirmed SO with a posted+paid invoice.

        The original invoice must be paid before refund processing, because
        Odoo 18 auto-reconciles credit notes with the reversed invoice on
        posting.  If the invoice is unpaid, the credit note fully reconciles
        it, leaving nothing for the refund payment wizard.
        """
        if product is None:
            product = self.product

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
                'tax_ids': [(6, 0, product.taxes_id.ids)],
                'integration_external_id': 'ext-line-1',
            })],
        })
        order.action_confirm()

        invoice = order.with_company(self.company)._create_invoices(final=True)
        if post_invoice:
            invoice.with_company(self.company).action_post()

        if post_invoice and pay_invoice:
            # Pay the invoice so it won't auto-reconcile with the credit note
            pay_wizard = self.env['account.payment.register'].with_context(
                active_ids=invoice.ids,
                active_model='account.move',
            ).create({
                'journal_id': self.bank_journal.id,
            })
            pay_wizard._create_payments()

        return order, invoice

    def _fill_line_taxes(self, order, line_vals):
        """Fill each refund line's ``total_tax`` from the matching sale order
        line's tax and return the GROSS refund total (Σ subtotal + Σ total_tax).

        A real platform refund payload carries, per line, a tax-EXCLUDED
        ``subtotal`` plus its own ``total_tax``, and the refund total is the
        gross amount the customer actually gets back. Computing the tax through
        Odoo's own ``compute_all`` — rather than a hard-coded rate — keeps the
        resulting credit note's recomputed ``amount_total`` equal to the refund
        total, so a faithful refund reconciles to zero and exits
        ``_apply_refund_total_adjustment`` through BOTH of its guards. That is
        what makes these fixtures honest: the no-adjustment path is exercised by
        realistic data, not by a net total paired with zero per-line tax (which
        would lean solely on the platform-line guard to stay green).

        Lines without ``total_tax`` are filled in place; the order's own tax is
        15% price-excluded, so passing the tax-excluded subtotal as the
        ``compute_all`` base is correct here.
        """
        gross = 0.0
        for lv in line_vals:
            so_line = order.order_line.filtered(
                lambda ln: ln.integration_external_id == lv['external_line_str_id']
            )[:1]
            res = so_line.tax_ids.compute_all(
                lv['subtotal'], currency=order.currency_id, quantity=1,
                product=so_line.product_id, partner=order.partner_id,
            )
            lv.setdefault('total_tax', res['total_included'] - res['total_excluded'])
            gross += lv['subtotal'] + lv['total_tax']
        return gross

    def _create_refund_record(
        self, order, total_amount=19.84, restock_type='no_restock',
        linked_return=None, currency=None, line_vals=None,
    ):
        """Helper: create an external.order.refund record with one line.

        With no explicit ``line_vals`` this builds a single faithful refund line
        for the order's product and derives the gross ``total_refunded_amount``
        from the line's tax via :meth:`_fill_line_taxes`, so the credit note
        reconciles to zero (the realistic case). ``total_amount`` is read as the
        tax-EXCLUDED line value in that path; pass explicit ``line_vals`` +
        ``total_amount`` to model a deliberate mismatch.
        """
        if currency is None:
            currency = order.currency_id

        refund_total = total_amount
        if line_vals is None:
            line_vals = [{
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
                'restock_type': restock_type,
                'original_unit_price': total_amount,
                'subtotal': total_amount,
                'currency_id': currency.id,
            }]
            refund_total = self._fill_line_taxes(order, line_vals)

        refund_vals = {
            'external_str_id': 'gid://shopify/Refund/test-%s' % order.id,
            'erp_order_id': order.id,
            'total_refunded_amount': refund_total,
            'currency_id': currency.id,
            'note': 'Test refund reason',
            'created_at_external': '2026-04-30 12:00:00',
        }
        if linked_return:
            refund_vals['linked_return_id'] = linked_return.id

        refund = self.env['external.order.refund'].create(refund_vals)

        for lv in line_vals:
            lv['refund_id'] = refund.id
            self.env['external.order.refund.line'].create(lv)

        return refund

    # --- Happy path ---

    def test_refund_creates_credit_note_and_payment(self):
        """Full happy path: confirmed order with paid invoice, refund with
        no linked return creates a posted credit note and refund payment.

        The refund is faithful (gross total = net subtotal + its tax), so the
        credit note total ties out to the money refunded and the payment fully
        reconciles it. Asserting amount_total / amount_residual here is what
        keeps the fixture honest: it proves no _apply_refund_total_adjustment
        line was needed because the books actually balance — not because a net
        total + zero per-line tax was quietly masked by the adjustment guard.
        """
        order, invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(order, total_amount=19.84)
        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')
        self.assertEqual(cn.state, 'posted', 'Credit note should be posted')
        self.assertTrue(refund.payment_ids, 'Refund payment should be created')
        self.assertEqual(
            cn.move_type, 'out_refund',
            'Credit note should be of type out_refund',
        )
        # The credit note total equals the gross refunded, and the refund
        # payment reconciles it to zero — no leftover residual.
        self.assertAlmostEqual(
            cn.amount_total, refund.total_refunded_amount, places=2,
            msg='Credit note total must equal the gross amount refunded',
        )
        self.assertAlmostEqual(
            cn.amount_residual, 0.0, places=2,
            msg='Refund payment must fully reconcile the credit note',
        )

    def test_refund_payment_uses_configured_payment_method_line(self):
        """_register_refund_payment() sets default_payment_method_line_id from the order's
        external payment method mapping, so the refund payment lands on the specifically
        configured payment method line — not whichever one account.payment.register would
        otherwise default to (its own default, absent this context, is the journal's first
        inbound line).
        """
        manual_pm = self.env['account.payment.method'].search([
            ('code', '=', 'manual'), ('payment_type', '=', 'inbound'),
        ], limit=1)
        other_line = self.env['account.payment.method.line'].create({
            'name': 'Refund Test Other Manual Line',
            'payment_method_id': manual_pm.id,
            'journal_id': self.bank_journal.id,
        })
        self.external_payment_method.payment_method_line_id = other_line.id

        order, invoice = self._create_confirmed_order_with_invoice()
        refund = self._create_refund_record(order, total_amount=19.84)
        refund._process()

        self.assertTrue(refund.payment_ids, 'Refund payment should be created')
        self.assertEqual(
            refund.payment_ids.payment_method_line_id, other_line,
            'Refund payment must use the payment method line configured on the '
            "order's external payment method, not the journal's default line.",
        )

    def test_refund_transaction_reconciled_when_linked_after_processing(self):
        """A REFUND-kind transaction that links to a refund only AFTER the refund
        was already processed (payment created, refund done) must still be marked
        done. The refund dispatch skips done refunds, so _register_refund_payment
        never re-runs — reconciliation happens at linkage time instead. Regression
        for refund transactions left stuck in Draft despite an applied refund.
        """
        order, invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(order, total_amount=19.84)
        refund._process()
        self.assertTrue(refund.payment_ids, 'Refund payment should be created')

        # The transaction is imported / linked only now — after the refund is done.
        txn = self.env['external.order.transaction'].create({
            'erp_order_id': order.id,
            'external_str_id': 'txn-refund-late',
            'kind': 'refund',
        })
        self.assertFalse(txn.is_done, 'New transaction starts in Draft')

        # Linking it to the already-processed refund and reconciling (what the
        # ingestion hook does on every re-import) must mark it done and attach the
        # refund payment — without re-registering a second payment.
        refund.transaction_ids = [(4, txn.id)]
        refund._reconcile_linked_transactions()

        self.assertTrue(
            txn.is_done,
            'Linked refund transaction must be marked done at linkage time',
        )
        self.assertEqual(
            txn.payment_ids, refund.payment_ids,
            'The refund payment must be attached to the transaction',
        )

    def test_refund_links_transaction_through_full_ingestion(self):
        """Regression: a refund-kind transaction must link to its refund when both
        arrive in the same _apply_values_from_external call (transactions created,
        then refund). The transaction's integration_id is a non-stored related on
        erp_order_id, so erp_order_id must be pre-bound at transaction-create time —
        otherwise it is still False when the refund's integration_id-filtered
        transaction lookup runs (erp_order_id is only set by the external_payment_ids
        O2M write afterwards), the lookup misses, and the transaction is left unlinked
        and stuck in Draft. Reproduces the production ingestion ordering, unlike the
        helper-level test which links the transaction by hand.
        """
        order, invoice = self._create_confirmed_order_with_invoice(
            qty=2, price_unit=19.84,
        )

        external_data = {
            'payment_transactions': [
                {'external_str_id': '900001', 'kind': 'sale', 'amount': '39.68',
                 'currency': 'EUR', 'external_status': 'success'},
                {'external_str_id': '900002', 'kind': 'refund', 'amount': '19.84',
                 'currency': 'EUR', 'external_status': 'success'},
            ],
            'order_refunds': [
                {'external_str_id': '700001', 'total_refunded_amount': 19.84,
                 'currency_code': 'EUR', 'transaction_str_ids': ['900002'],
                 'lines': [{'external_line_str_id': 'ext-line-1', 'quantity': 1,
                            'restock_type': 'no_restock', 'original_unit_price': 19.84,
                            'subtotal': 19.84, 'currency_code': 'EUR'}]},
            ],
        }
        # Skip the fresh-import dispatch job — we are asserting the ingestion-time
        # linkage only, which happens in _get_or_create_from_external regardless.
        order.with_context(
            skip_external_entity_dispatch=True,
        )._apply_values_from_external(external_data)

        refund = order.external_refund_ids
        self.assertEqual(len(refund), 1)
        refund_txn = order.external_payment_ids.filtered(
            lambda t: t.kind == 'refund'
        )
        self.assertEqual(len(refund_txn), 1)
        self.assertIn(
            refund_txn, refund.transaction_ids,
            'Refund must link the refund-kind transaction at ingestion time',
        )

    def test_reconcile_linked_transactions_noop_for_unprocessed_refund(self):
        """Reconciliation is a no-op while the refund is still unprocessed (no
        payment): a linked transaction must NOT be marked done prematurely."""
        order, invoice = self._create_confirmed_order_with_invoice()
        refund = self._create_refund_record(order, total_amount=19.84)

        txn = self.env['external.order.transaction'].create({
            'erp_order_id': order.id,
            'external_str_id': 'txn-refund-pending',
            'kind': 'refund',
        })
        refund.transaction_ids = [(4, txn.id)]

        self.assertFalse(refund.payment_ids)
        refund._reconcile_linked_transactions()
        self.assertFalse(
            txn.is_done,
            'Transaction must stay Draft until the refund is actually processed',
        )

    def test_refund_processed_on_cancelled_order(self):
        """A refund that arrives AFTER the order was cancelled in Odoo must still be
        processed: a cancelled order keeps its posted + paid invoice, so the credit
        note + refund payment are created and the refund transaction is marked done.

        Regression: the per-order processing dispatch was enqueued only for confirmed
        orders, so a refund ingested onto a cancelled order created the refund record
        but never dispatched it — leaving the refund unapplied and its refund
        transaction stuck in Draft. Cancelled orders now dispatch refunds (only).
        """
        # Tax-free product so the credit note ties out to the refund total exactly.
        product = self.env['product.product'].with_company(self.company).create({
            'name': 'Cancel-Refund Product',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 20.0,
            'taxes_id': [(5, 0, 0)],
        })
        order, _invoice = self._create_confirmed_order_with_invoice(
            product=product, qty=1, price_unit=20.0,
        )

        # Cancel the order in Odoo — the posted + paid invoice survives (_action_cancel
        # only cancels DRAFT invoices), which is exactly what makes the refund processable.
        order._action_cancel()
        self.assertEqual(order.state, 'cancel')

        ccy = order.currency_id.name
        external_data = {
            'payment_transactions': [
                {'external_str_id': '900002', 'kind': 'refund', 'amount': '20.00',
                 'currency': ccy, 'external_status': 'success'},
            ],
            'order_refunds': [
                {'external_str_id': '700001', 'total_refunded_amount': 20.0,
                 'currency_code': ccy, 'transaction_str_ids': ['900002'],
                 'lines': [{'external_line_str_id': 'ext-line-1', 'quantity': 1,
                            'restock_type': 'no_restock', 'original_unit_price': 20.0,
                            'subtotal': 20.0, 'currency_code': ccy}]},
            ],
        }
        # Production ingestion path — NOT skip_external_entity_dispatch. queue_job__no_delay
        # (set on the base env) runs the enqueued dispatch synchronously.
        order._apply_values_from_external(external_data)

        refund = order.external_refund_ids
        self.assertEqual(len(refund), 1)
        self.assertTrue(
            refund.credit_note_id,
            'Refund on a cancelled order must be processed (credit note created)',
        )
        self.assertEqual(refund.credit_note_id.state, 'posted')
        self.assertTrue(refund.payment_ids, 'Refund payment must be registered')

        refund_txn = order.external_payment_ids.filtered(lambda t: t.kind == 'refund')
        self.assertEqual(len(refund_txn), 1)
        self.assertTrue(
            refund_txn.is_done,
            'Refund transaction must be marked done once the refund is processed',
        )

    def test_partial_shipping_refund_credits_delivery_line(self):
        """A refund covering a product line + a partial shipping fee must KEEP the
        credit note's delivery line (set to the refunded shipping amount), so the
        credit note total equals total_refunded_amount and the refund payment
        reconciles with no floating difference. Regression for shipping refunds
        being dropped from the credit note (WooCommerce shipping_lines).
        """
        # Tax-free product + delivery product so the amounts are exact.
        product = self.env['product.product'].with_company(self.company).create({
            'name': 'Shipping-Test Product',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 18.0,
            'taxes_id': [(5, 0, 0)],
        })
        delivery_product = self.env['product.product'].with_company(self.company).create({
            'name': 'Flat Rate Delivery',
            'type': 'service',
            'invoice_policy': 'order',
            'taxes_id': [(5, 0, 0)],
        })

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 2,
                    'price_unit': 18.0,
                    'tax_ids': [(5, 0, 0)],
                    'integration_external_id': 'ext-line-1',
                }),
                (0, 0, {
                    'product_id': delivery_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 11.90,
                    'tax_ids': [(5, 0, 0)],
                    'is_delivery': True,
                    'integration_external_id': 'ext-ship-1',
                }),
            ],
        })
        order.action_confirm()
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        pay = self.env['account.payment.register'].with_context(
            active_ids=invoice.ids, active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})
        pay._create_payments()

        # Refund: 1 of 2 products (18.00) + partial shipping (5.95) = 23.95.
        refund = self._create_refund_record(order, total_amount=23.95, line_vals=[
            {
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 18.0,
                'subtotal': 18.0,
                'currency_id': order.currency_id.id,
            },
            {
                'is_shipping': True,
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 5.95,
                'subtotal': 5.95,
                'currency_id': order.currency_id.id,
            },
        ])
        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')
        product_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
        )
        delivery_cn = product_lines.filtered(
            lambda ln: ln.sale_line_ids.filtered('is_delivery')
        )
        self.assertEqual(
            len(delivery_cn), 1,
            'Credit note must KEEP the delivery line for the shipping refund',
        )
        self.assertAlmostEqual(
            delivery_cn.price_unit, 5.95, places=2,
            msg='Delivery line must be set to the refunded shipping amount',
        )
        # The product line is kept too (1 product + 1 delivery line).
        self.assertEqual(len(product_lines - delivery_cn), 1)
        # Credit note total equals the refund amount → payment reconciles fully,
        # no 5.95 floating on the refund payment.
        self.assertAlmostEqual(cn.amount_total, 23.95, places=2)
        self.assertAlmostEqual(cn.amount_residual, 0.0, places=2)

    def test_shipping_refund_with_tax_included_uses_gross_price(self):
        """When the delivery line carries a price-INCLUDED tax (EU/PL VAT), the
        shipping refund line's price_unit on the credit note must be the GROSS
        amount (subtotal + tax). The connectors store the refunded shipping as a
        tax-EXCLUDED subtotal + separate tax; for a tax-inclusive line Odoo derives
        the net FROM price_unit, so using the net subtotal as price_unit would
        wrongly shrink the net by the tax fraction (e.g. 4.87 → 3.96). Reproduces
        the Shopify #1685 case (shipping 4.87 net + 1.12 tax = 5.99 gross).
        """
        tax_incl = self.env['account.tax'].with_company(self.company).create({
            'name': 'VAT 23 incl',
            'amount': 23.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })
        product = self.env['product.product'].with_company(self.company).create({
            'name': 'Incl Product',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 51.0,
            'taxes_id': [(6, 0, tax_incl.ids)],
        })
        delivery_product = self.env['product.product'].with_company(self.company).create({
            'name': 'Incl Delivery',
            'type': 'service',
            'invoice_policy': 'order',
            'taxes_id': [(6, 0, tax_incl.ids)],
        })
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': [
                (0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'price_unit': 51.0,
                    'tax_ids': [(6, 0, tax_incl.ids)],
                    'integration_external_id': 'ext-line-1',
                }),
                (0, 0, {
                    'product_id': delivery_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 5.99,
                    'tax_ids': [(6, 0, tax_incl.ids)],
                    'is_delivery': True,
                    'integration_external_id': 'ext-ship-1',
                }),
            ],
        })
        order.action_confirm()
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        pay = self.env['account.payment.register'].with_context(
            active_ids=invoice.ids, active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})
        pay._create_payments()

        # Full refund: product 51.00 (gross) + shipping 4.87 net + 1.12 tax = 56.99.
        refund = self._create_refund_record(order, total_amount=56.99, line_vals=[
            {
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 51.0,
                'subtotal': 51.0,
                'currency_id': order.currency_id.id,
            },
            {
                'is_shipping': True,
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 4.87,
                'subtotal': 4.87,
                'total_tax': 1.12,
                'currency_id': order.currency_id.id,
            },
        ])
        refund._process()

        cn = refund.credit_note_id
        delivery_cn = cn.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
            and ln.sale_line_ids.filtered('is_delivery')
        )
        self.assertEqual(len(delivery_cn), 1)
        # price_unit is the GROSS shipping (5.99); the net subtotal is the refunded
        # 4.87 — NOT 3.96 (which is what a net price_unit would wrongly produce).
        self.assertAlmostEqual(delivery_cn.price_unit, 5.99, places=2)
        self.assertAlmostEqual(delivery_cn.price_subtotal, 4.87, places=2)
        # Whole credit note ties out to the refunded amount, payment reconciles.
        self.assertAlmostEqual(cn.amount_total, 56.99, places=2)
        self.assertAlmostEqual(cn.amount_residual, 0.0, places=2)

    def test_discount_refund_creates_two_credit_note_lines(self):
        """Refund with discount (subtotal < original_unit_price * qty)
        creates a credit note with product line + negative discount line."""
        order, invoice = self._create_confirmed_order_with_invoice(
            price_unit=19.84,
        )

        # Faithful refund: net subtotal 12.34 (after a 7.50 discount) plus its
        # own tax, gross total derived from the order's tax so the credit note
        # reconciles and the adjustment guard is not involved.
        line_vals = [{
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
            'restock_type': 'no_restock',
            'original_unit_price': 19.84,
            'subtotal': 12.34,
            'currency_id': order.currency_id.id,
        }]
        gross = self._fill_line_taxes(order, line_vals)
        refund = self._create_refund_record(
            order, total_amount=gross, line_vals=line_vals,
        )

        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')

        product_lines = cn.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
        )
        self.assertEqual(
            len(product_lines), 2,
            'Credit note should have 2 product lines (product + discount)',
        )

        # One line should be the product at 19.84, one should be discount at -7.50
        prices = sorted(product_lines.mapped('price_unit'))
        self.assertAlmostEqual(
            prices[0], -7.50, places=2,
            msg='Discount line should be -7.50',
        )
        self.assertAlmostEqual(
            prices[1], 19.84, places=2,
            msg='Product line should be 19.84',
        )

    # --- Placeholder / zero-amount ---

    def test_placeholder_refund_with_linked_return_is_skipped(self):
        """Refund with amount=0 and a linked return is a placeholder for the
        'process return now, refund later' workflow. No credit note is
        created; the record is marked skipped."""
        order, invoice = self._create_confirmed_order_with_invoice()

        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/test-1',
            'erp_order_id': order.id,
        })

        refund = self._create_refund_record(
            order, total_amount=0, linked_return=ret,
        )

        refund._process()

        self.assertFalse(
            refund.credit_note_id,
            'No credit note should be created for placeholder',
        )
        self.assertEqual(
            refund.internal_status, 'skipped',
            'Placeholder refund should be marked as skipped',
        )

    def test_placeholder_refund_via_validate_ends_skipped_with_note(self):
        """Regression for the user-visible bug: the production path is validate()
        (called from dispatch), which used to overwrite the placeholder's
        'skipped' status with 'done'. The record then showed Done with a 0
        amount and no credit note — looking like a bug. It must now end
        'skipped' and carry a plain-language Processing Note that explains the
        'refund later' placeholder."""
        order, _invoice = self._create_confirmed_order_with_invoice()
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/test-ph',
            'erp_order_id': order.id,
        })
        refund = self._create_refund_record(
            order, total_amount=0, linked_return=ret,
        )

        result, _ids = refund.validate()

        self.assertTrue(result)
        self.assertEqual(
            refund.internal_status, 'skipped',
            'Placeholder must end skipped via the production validate() path, '
            'not done',
        )
        self.assertFalse(refund.credit_note_id)
        self.assertTrue(refund.is_placeholder)
        self.assertIn('refund later', (refund.internal_info or '').lower())

    def test_skipped_refund_not_reprocessed_on_revalidate(self):
        """A skipped record is terminal: re-validating it (as dispatch does on
        the next webhook) is a no-op and must not reprocess it or wipe the
        explanatory note. Guards both placeholders and the manual Skip button."""
        order, _invoice = self._create_confirmed_order_with_invoice()
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/test-ph2',
            'erp_order_id': order.id,
        })
        refund = self._create_refund_record(
            order, total_amount=0, linked_return=ret,
        )
        refund.validate()
        note = refund.internal_info

        refund.validate()
        self.assertEqual(refund.internal_status, 'skipped')
        self.assertEqual(
            refund.internal_info, note,
            'Re-validating a skipped record must preserve its note',
        )
        self.assertFalse(refund.credit_note_id)

    def test_zero_refund_without_linked_return_raises_13(self):
        """Refund with zero amount and no linked return is anomalous and must
        fail-loud rather than silently skip."""
        order, invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(order, total_amount=0)

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E513', cm.exception.args[0])

    # --- Invoice prerequisite guards ---

    def test_no_invoice_raises_2a(self):
        """Refund on an order with no invoice soft-fails via PrerequisiteNotMet.
        Retried by the lifecycle hook when an invoice is posted."""
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 19.84,
                'tax_ids': [(6, 0, self.product.taxes_id.ids)],
                'integration_external_id': 'ext-line-1',
            })],
        })
        order.action_confirm()

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(PrerequisiteNotMet) as cm:
            refund._process()
        self.assertIn('E503', str(cm.exception))

    def test_draft_invoice_raises_2(self):
        """Refund on an order with only a draft invoice soft-fails via
        PrerequisiteNotMet. Retried by the lifecycle hook when the invoice
        is posted."""
        order, invoice = self._create_confirmed_order_with_invoice(
            post_invoice=False, pay_invoice=False,
        )

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(PrerequisiteNotMet) as cm:
            refund._process()
        self.assertIn('E502', str(cm.exception))

    def test_unresolvable_refund_line_raises_1(self):
        """Refund line referencing an unknown external_line_str_id (product
        not on any posted invoice) fails-loud. Resolution does NOT fall back
        to SKU search — only the external id is consulted."""
        order, invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(
            order, total_amount=25.00, line_vals=[{
                'external_line_str_id': 'ext-line-UNKNOWN',
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 25.00,
                'subtotal': 25.00,
                'currency_id': order.currency_id.id,
            }],
        )

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E501', cm.exception.args[0])

    def test_missing_refund_journal_raises_3(self):
        """Refund fails-loud when the order's payment method has no journal
        configured (in this scenario the order has no payment method at all).
        """
        integration_no_journal = self._create_test_integration(
            'No-Journal Integration', enable_returns_refunds_sync=False,
        )

        order, invoice = self._create_confirmed_order_with_invoice()
        # Clear the order's payment method so the journal-resolution chain
        # has nothing to read.
        order.write({
            'integration_id': integration_no_journal.id,
            'payment_method_id': False,
        })

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E504', cm.exception.args[0])

    def test_manual_credit_note_blocks_processing_9(self):
        """A manually-created credit note (not linked to any
        external.order.refund) on the order blocks refund processing to
        prevent double crediting."""
        order, invoice = self._create_confirmed_order_with_invoice()

        # Create a manual (unlinked) credit note on the order
        manual_cn = self.env['account.move.reversal'].with_context(
            active_model='account.move',
            active_ids=[invoice.id],
        ).create({
            'reason': 'Manual refund',
            'journal_id': invoice.journal_id.id,
        })
        manual_cn.refund_moves()

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E509', cm.exception.args[0])

    # --- Payment state guards ---

    def test_unpaid_posted_invoice_raises_14(self):
        """Posted but unpaid invoice soft-fails via PrerequisiteNotMet.
        Retried by the lifecycle hook when payment is registered."""
        order, invoice = self._create_confirmed_order_with_invoice(
            post_invoice=True, pay_invoice=False,
        )

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(PrerequisiteNotMet) as cm:
            refund._process()
        self.assertIn('E514', str(cm.exception))

        # No credit note was created
        self.assertFalse(
            refund.credit_note_id,
            'No credit note should be created when invoice is unpaid',
        )

    def test_partial_payment_with_residual_raises_14(self):
        """Defense-in-depth: an invoice with non-zero residual soft-fails via
        PrerequisiteNotMet even when payment_state would suggest "paid". Catches
        edge cases where payment_state='in_payment' coexists with an outstanding
        balance (in-process providers, installment payment terms).
        """
        order, invoice = self._create_confirmed_order_with_invoice(
            post_invoice=True, pay_invoice=False, qty=2,
        )

        pay_wizard = self.env['account.payment.register'].with_context(
            active_ids=invoice.ids,
            active_model='account.move',
        ).create({
            'journal_id': self.bank_journal.id,
            'amount': invoice.amount_total / 2,
        })
        pay_wizard._create_payments()

        self.assertGreater(
            invoice.amount_residual, 0,
            'Sanity: invoice must have residual > 0 after partial payment',
        )
        # Guard catches both 'partial' and 'in_payment' scenarios
        self.assertIn(
            invoice.payment_state, ('partial', 'in_payment'),
            'Sanity: payment_state must be partial or in_payment',
        )

        refund = self._create_refund_record(order, total_amount=19.84)

        with self.assertRaises(PrerequisiteNotMet) as cm:
            refund._process()
        # Both partial-payment sub-cases (the regular "posted but not paid"
        # branch and the "in_payment with residual" defense-in-depth branch)
        # share the same catalog code — the test no longer needs an OR.
        self.assertIn('E514', str(cm.exception))

        self.assertFalse(
            refund.credit_note_id,
            'No credit note should be created when invoice has residual',
        )

    # --- Currency mismatch guard ---

    def test_currency_mismatch_raises_5_without_credit_note(self):
        """Currency mismatch must be caught before credit note creation —
        otherwise the posted credit note would auto-reconcile with the
        invoice and require manual cleanup. No orphan credit note should
        exist on the order."""
        order, invoice = self._create_confirmed_order_with_invoice()

        other_currency = self.currency_eur
        if other_currency == order.currency_id:
            other_currency = self.env.ref('base.GBP')
            other_currency.active = True

        refund = self._create_refund_record(
            order, total_amount=19.84, currency=other_currency,
        )

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E506', cm.exception.args[0])

        # No credit note was created (check moved before wizard invocation)
        self.assertFalse(
            refund.credit_note_id,
            'No credit note should be created when currency mismatches',
        )

        # No orphan out_refund moves on the order
        refund_moves = order.invoice_ids.filtered(
            lambda m: m.move_type == 'out_refund'
        )
        self.assertFalse(
            refund_moves,
            'No orphan credit note should exist on the order',
        )

    # --- Archived currency resolution ---

    def test_prepare_vals_from_external_resolves_archived_currency(self):
        """_prepare_vals_from_external must resolve currency_code even when that
        currency is archived in Odoo — res.currency.search() only sees active
        currencies by default, so an archived one used to leave currency_id unset
        (silently, not fail-loud), letting the credit note post in the invoice's
        currency instead of the refund's. Covers both the refund-level and the
        line-level currency_code lookup.
        """
        self.currency_eur.active = False

        data = {
            'currency_code': 'EUR',
            'lines': [{
                'external_line_str_id': 'ext-line-a',
                'quantity': 1,
                'currency_code': 'EUR',
            }],
        }

        vals = self.env['external.order.refund']._prepare_vals_from_external(data)

        self.assertEqual(
            vals.get('currency_id'), self.currency_eur.id,
            'Refund-level currency_code must resolve to the archived currency.',
        )
        self.assertEqual(
            vals['line_ids'][1][2].get('currency_id'), self.currency_eur.id,
            'Line-level currency_code must resolve to the archived currency.',
        )

    # --- Idempotency (M-1 + M-2) ---

    def test_reprocessing_refund_does_not_duplicate_credit_note_or_payment(self):
        """_create_credit_note() and _register_refund_payment() short-circuit
        when their target record already exists on the refund. Re-running
        _process() — as the dispatch retry mechanism may do —
        must not create a second credit note or a second payment."""
        order, _invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(order, total_amount=19.84)
        refund._process()

        original_cn = refund.credit_note_id
        original_payments = refund.payment_ids
        self.assertTrue(original_cn, 'First _process() should create a credit note')
        self.assertEqual(
            len(original_payments), 1,
            'First _process() should create exactly one refund payment',
        )

        refund._process()

        self.assertEqual(
            refund.credit_note_id, original_cn,
            'Re-processing must not replace the credit note',
        )
        self.assertEqual(
            len(refund.payment_ids), 1,
            'Re-processing must not register a second refund payment',
        )

        # Order should have exactly one out_refund move on it.
        refund_moves = order.invoice_ids.filtered(
            lambda m: m.move_type == 'out_refund'
        )
        self.assertEqual(
            len(refund_moves), 1,
            'Order must have exactly one credit note after re-processing',
        )

    # --- Multi-line refund with mixed discount (M-9) ---

    def test_multi_line_refund_with_mixed_discount(self):
        """Refund covering multiple products, where only some lines have a
        discount, exercises the matching loop in _adjust_credit_note_lines:
        matched lines get qty/price overrides, unmatched ones are dropped,
        and discount sublines are appended only for the lines that need them.
        """
        # Create an order with two lines and invoice both in a single invoice.
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': [
                (0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 19.84,
                    'tax_ids': [(6, 0, self.product.taxes_id.ids)],
                    'integration_external_id': 'ext-line-1',
                }),
                (0, 0, {
                    'product_id': self.product_b.id,
                    'product_uom_qty': 1,
                    'price_unit': 25.00,
                    'tax_ids': [(6, 0, self.product_b.taxes_id.ids)],
                    'integration_external_id': 'ext-line-2',
                }),
            ],
        })
        order.action_confirm()
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        pay_wizard = self.env['account.payment.register'].with_context(
            active_ids=invoice.ids,
            active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})
        pay_wizard._create_payments()

        # Refund both lines; only the second line carries a discount
        # (subtotal=20.00 vs original=25.00 → discount_for_refund=5.00).
        # Net subtotals + per-line tax + gross total derived from the order's
        # tax, so the refund is faithful and the adjustment guard is not hit.
        line_vals = [
            {
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 19.84,
                'subtotal': 19.84,
                'currency_id': order.currency_id.id,
            },
            {
                'external_line_str_id': 'ext-line-2',
                'quantity': 1,
                'restock_type': 'no_restock',
                'original_unit_price': 25.00,
                'subtotal': 20.00,
                'currency_id': order.currency_id.id,
            },
        ]
        gross = self._fill_line_taxes(order, line_vals)
        refund = self._create_refund_record(
            order, total_amount=gross, line_vals=line_vals,
        )
        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')

        product_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
        )
        # Two product lines (one per refund line) + one negative discount line
        # for the discounted line only.
        self.assertEqual(
            len(product_lines), 3,
            'Expected 2 product lines + 1 discount line on the credit note',
        )

        # The original products must both appear with their full unit prices.
        prices_by_product = {
            ln.product_id: ln.price_unit for ln in product_lines
        }
        self.assertAlmostEqual(
            prices_by_product[self.product], 19.84, places=2,
            msg='product line should reflect original unit price',
        )
        self.assertAlmostEqual(
            prices_by_product[self.product_b], 25.00, places=2,
            msg='product_b line should reflect original unit price',
        )
        self.assertAlmostEqual(
            prices_by_product[self.discount_product], -5.00, places=2,
            msg='discount line should be -5.00 (only for the discounted line)',
        )

    # --- Multi-invoice resolution (H-6) ---

    def test_refund_routes_to_correct_invoice_when_multiple_paid(self):
        """When the order has multiple paid invoices (each covering a different
        subset of the refunded products), _resolve_original_invoice() must pick
        the invoice that actually contains the refunded product — not just the
        newest one. The bug class this prevents: silent credit-note routing to
        the wrong receivable on multi-shipment / split-invoice orders."""
        # invoice_a — older — covers `product` (ext-line-1) only.
        order, invoice_a = self._create_confirmed_order_with_invoice(
            product=self.product, qty=1, price_unit=19.84,
        )

        # Add a second SO line for product_b and invoice ONLY that line.
        # _create_invoices skips line_a because its qty_to_invoice is already 0
        # after invoice_a was created.
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_b.id,
            'product_uom_qty': 1,
            'price_unit': 25.00,
            'tax_ids': [(6, 0, self.product_b.taxes_id.ids)],
            'integration_external_id': 'ext-line-2',
        })
        invoice_b = order.with_company(self.company)._create_invoices(final=True)
        invoice_b.with_company(self.company).action_post()
        pay_wizard = self.env['account.payment.register'].with_context(
            active_ids=invoice_b.ids,
            active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})
        pay_wizard._create_payments()

        self.assertNotEqual(
            invoice_a.id, invoice_b.id,
            'Sanity: two distinct invoices must exist on the order',
        )
        self.assertIn(invoice_a.payment_state, ('paid', 'in_payment'))
        self.assertIn(invoice_b.payment_state, ('paid', 'in_payment'))

        # Refund the line that lives on invoice_a (the OLDER invoice).
        # Iteration order is newest-first, so a naive "pick newest" picker
        # would land on invoice_b and miss the product entirely. Faithful
        # refund (net subtotal + tax + gross total) so the credit note ties out.
        line_vals = [{
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
            'restock_type': 'no_restock',
            'original_unit_price': 19.84,
            'subtotal': 19.84,
            'currency_id': order.currency_id.id,
        }]
        gross = self._fill_line_taxes(order, line_vals)
        refund = self._create_refund_record(
            order, total_amount=gross, line_vals=line_vals,
        )
        refund._process()

        self.assertTrue(refund.credit_note_id, 'Credit note should be created')
        self.assertEqual(
            refund.credit_note_id.reversed_entry_id, invoice_a,
            'Credit note must reverse invoice_a (older, contains the refunded '
            'product), not invoice_b (newer, contains a different product).',
        )

    # --- Lineless refund (H-4) ---

    def test_lineless_refund_uses_refund_product(self):
        """When the platform sends a flat refund amount with no line-item
        breakdown, _adjust_credit_note_lines_lineless() replaces the wizard's
        reversal lines with a single line on the integration's configured
        Refund Product. Reaches a production-only code path."""
        # Configure refund_product_id on the integration
        refund_product = self.env['product.product'].with_company(
            self.company,
        ).create({
            'name': 'Generic Refund Product',
            'default_code': 'GENERIC_REFUND',
            'type': 'service',
            'taxes_id': [(5, 0, 0)],
        })
        self.integration.refund_product_id = refund_product.id
        self.addCleanup(
            self.integration.write, {'refund_product_id': False},
        )

        order, _invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(
            order, total_amount=19.84, line_vals=[],
        )
        self.assertFalse(refund.line_ids, 'Sanity: refund must be lineless')

        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')
        product_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
        )
        self.assertEqual(
            len(product_lines), 1,
            'Lineless refund must produce exactly one credit-note line',
        )
        self.assertEqual(
            product_lines.product_id, refund_product,
            'The single line must reference the integration\'s refund product',
        )
        self.assertAlmostEqual(
            product_lines.price_unit, 19.84, places=2,
            msg='Line amount must match total_refunded_amount',
        )

    def test_lineless_refund_without_refund_product_raises(self):
        """Lineless refund must fail-loud with an actionable message when
        the integration has no Refund Product configured — otherwise the
        flow would silently drop the credit-note line and post a zero-amount
        credit note."""
        # Ensure refund_product_id is NOT set on the integration
        self.integration.refund_product_id = False

        order, _invoice = self._create_confirmed_order_with_invoice()

        refund = self._create_refund_record(
            order, total_amount=19.84, line_vals=[],
        )

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E553', cm.exception.args[0])

    # --- linked_return_str_id → linked_return_id resolution end-to-end ---

    def test_uc2b_ingestion_resolves_linked_return_and_skips_placeholder(self):
        """End-to-end UC-2b: a Shopify-shaped payload with a closed return and
        a zero-amount refund pointing at that return via linked_return_str_id
        must (a) resolve linked_return_id at ingestion (returns ingested first
        in sale_order._apply_values_from_external) so is_placeholder=True, and
        (b) short-circuit _process to mark_skipped — no credit note created."""
        order, _invoice = self._create_confirmed_order_with_invoice()

        external_data = {
            'order_returns': [{
                'external_str_id': 'gid://shopify/Return/uc2b-1',
                'state': 'closed',
                'lines': [{
                    'external_line_str_id': 'ext-line-1',
                    'quantity': 1,
                }],
            }],
            'order_refunds': [{
                'external_str_id': 'gid://shopify/Refund/uc2b-1',
                'total_refunded_amount': 0,
                'currency_code': order.currency_id.name,
                'linked_return_str_id': 'gid://shopify/Return/uc2b-1',
                'lines': [],
            }],
        }

        order.with_context(
            skip_external_entity_dispatch=True,
        )._apply_values_from_external(external_data)

        self.assertEqual(len(order.external_return_ids), 1)
        self.assertEqual(len(order.external_refund_ids), 1)

        ret = order.external_return_ids
        refund = order.external_refund_ids

        self.assertEqual(
            refund.linked_return_id, ret,
            'Refund.linked_return_id must resolve to the return ingested in '
            'the same _apply_values_from_external call',
        )
        self.assertTrue(
            refund.is_placeholder,
            'Zero-amount refund with linked_return is a placeholder',
        )

        refund._process()

        self.assertEqual(
            refund.internal_status, 'skipped',
            'Placeholder refund must be marked skipped, not left in draft',
        )
        self.assertFalse(
            refund.credit_note_id,
            'No credit note should be created for placeholder refund',
        )

    # --- restock_type=CANCEL contradiction (M-8) ---

    def test_refund_with_cancel_restock_and_linked_return_raises(self):
        """restock_type=CANCEL semantically means "this line was never shipped"
        — it only makes sense for unfulfilled orders. If the platform also
        attaches a linked_return (which implies the order WAS fulfilled),
        the payload is contradictory and must fail-loud rather than guess."""
        order, _invoice = self._create_confirmed_order_with_invoice()

        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/cancel-contradiction',
            'erp_order_id': order.id,
        })

        refund = self._create_refund_record(
            order, total_amount=19.84, linked_return=ret,
            restock_type='cancel',
        )

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E551', cm.exception.args[0])

    # --- Refund total mismatch / adjustment line (D-62, E555) ---

    def _create_mismatch_order(self, prices, ext_ids):
        """Confirmed SO with N tax-free product lines, invoice posted + paid.

        Tax-free so the credit note total equals the sum of the line nets and the
        adjustment math is exact. Returns (order, [products]).
        """
        lines = []
        products = []
        for price, ext in zip(prices, ext_ids):
            product = self.env['product.product'].with_company(self.company).create({
                'name': 'Mismatch Product %s' % ext,
                'type': 'consu',
                'invoice_policy': 'order',
                'list_price': price,
                'taxes_id': [(5, 0, 0)],
            })
            products.append(product)
            lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
                'integration_external_id': ext,
            }))

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': lines,
        })
        order.action_confirm()
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        pay = self.env['account.payment.register'].with_context(
            active_ids=invoice.ids, active_model='account.move',
        ).create({'journal_id': self.bank_journal.id})
        pay._create_payments()
        return order, products

    def _set_adjustment_product(self):
        """Configure a tax-free service adjustment product on the integration."""
        product = self.env['product.product'].with_company(self.company).create({
            'name': 'Refund Adjustment',
            'type': 'service',
            'taxes_id': [(5, 0, 0)],
        })
        self.integration.refund_adjustment_product_id = product.id
        return product

    @staticmethod
    def _refund_line(ext_id, price):
        return {
            'external_line_str_id': ext_id,
            'quantity': 1,
            'restock_type': 'no_restock',
            'original_unit_price': price,
            'subtotal': price,
        }

    def test_refund_adjustment_added_when_mismatch_and_product_set(self):
        """The Shopify #1701 scenario: line items sum to 29 (Beanie 20 + Sugar 9)
        but the merchant adjusted the refund total down to 20. With an adjustment
        product configured, a tax-free -9 adjustment line is appended so the credit
        note totals 20, the payment reconciles fully, and the adjustment is recorded
        in chatter.
        """
        order, _products = self._create_mismatch_order([20.0, 9.0], ['beanie', 'sugar'])
        adjustment_product = self._set_adjustment_product()

        refund = self._create_refund_record(order, total_amount=20.0, line_vals=[
            self._refund_line('beanie', 20.0),
            self._refund_line('sugar', 9.0),
        ])
        refund._process()

        cn = refund.credit_note_id
        self.assertTrue(cn, 'Credit note should be created')

        adjustment_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.product_id == adjustment_product
        )
        self.assertEqual(len(adjustment_lines), 1, 'Exactly one adjustment line')
        self.assertAlmostEqual(
            adjustment_lines.price_unit, -9.0, places=2,
            msg='Adjustment must be the signed difference (20 - 29 = -9)',
        )
        self.assertFalse(adjustment_lines.tax_ids, 'Adjustment line carries no tax')

        # 2 product lines + 1 adjustment line.
        self.assertEqual(
            len(cn.invoice_line_ids.filtered(lambda ln: ln.display_type == 'product')),
            3,
        )
        # Credit note now matches the money refunded → payment reconciles fully.
        self.assertAlmostEqual(cn.amount_total, 20.0, places=2)
        self.assertAlmostEqual(cn.amount_residual, 0.0, places=2)
        self.assertTrue(refund.payment_ids, 'Refund payment should be created')

        # Audit trail in chatter.
        adjustment_msgs = [m for m in cn.message_ids if 'Adjustment line added' in (m.body or '')]
        self.assertTrue(adjustment_msgs, 'A chatter message must document the adjustment')

        # The message also points at the likely cause. An adjustment is usually deliberate, but
        # when it is not, the merchant needs to know where to look — the discrepancy originates in
        # the platform, not in Odoo.
        self.assertIn(
            'manually overridden refund total', adjustment_msgs[0].body,
            'The adjustment message must explain the likely cause of an unexpected discrepancy',
        )

    def test_refund_adjustment_fails_loud_when_product_not_set(self):
        """Same mismatch, but no adjustment product configured → fail loud (E555),
        no posted credit note left behind."""
        order, _products = self._create_mismatch_order([20.0, 9.0], ['beanie', 'sugar'])
        # Deliberately do NOT set refund_adjustment_product_id.
        self.assertFalse(self.integration.refund_adjustment_product_id)

        refund = self._create_refund_record(order, total_amount=20.0, line_vals=[
            self._refund_line('beanie', 20.0),
            self._refund_line('sugar', 9.0),
        ])

        with self.assertRaises(UserError) as cm:
            refund._process()
        self.assertIn('E555', cm.exception.args[0])

    def test_no_adjustment_when_totals_match(self):
        """When the line items sum to the refund total, no adjustment line is added
        and no adjustment chatter is posted — even with an adjustment product
        configured (proving it's the match, not a missing product, that's decisive).
        """
        order, _products = self._create_mismatch_order([20.0, 9.0], ['beanie', 'sugar'])
        adjustment_product = self._set_adjustment_product()

        refund = self._create_refund_record(order, total_amount=29.0, line_vals=[
            self._refund_line('beanie', 20.0),
            self._refund_line('sugar', 9.0),
        ])
        refund._process()

        cn = refund.credit_note_id
        self.assertFalse(
            cn.invoice_line_ids.filtered(lambda ln: ln.product_id == adjustment_product),
            'No adjustment line when totals match',
        )
        self.assertAlmostEqual(cn.amount_total, 29.0, places=2)
        self.assertFalse(
            any('Adjustment line added' in (m.body or '') for m in cn.message_ids),
            'No adjustment chatter when totals match',
        )

    def test_positive_adjustment_when_refund_exceeds_lines(self):
        """Refund total (25) exceeds the line items (20) → a positive +5 adjustment
        line is added so the credit note grows to match the money refunded."""
        order, _products = self._create_mismatch_order([20.0], ['beanie'])
        adjustment_product = self._set_adjustment_product()

        refund = self._create_refund_record(order, total_amount=25.0, line_vals=[
            self._refund_line('beanie', 20.0),
        ])
        refund._process()

        cn = refund.credit_note_id
        adjustment_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.product_id == adjustment_product
        )
        self.assertEqual(len(adjustment_lines), 1)
        self.assertAlmostEqual(
            adjustment_lines.price_unit, 5.0, places=2,
            msg='Refund exceeds lines → positive adjustment (25 - 20 = +5)',
        )
        self.assertAlmostEqual(cn.amount_total, 25.0, places=2)

    def test_adjustment_line_has_no_tax(self):
        """The adjustment line must carry no tax even when the refunded product
        lines are taxed (the adjustment is a pure monetary reconciliation)."""
        # Taxed product so the product credit note line carries tax.
        order, _invoice = self._create_confirmed_order_with_invoice(
            product=self.product, qty=1, price_unit=19.84,
        )
        adjustment_product = self._set_adjustment_product()

        # Force a mismatch: refund total well below the taxed line total.
        refund = self._create_refund_record(order, total_amount=10.0, line_vals=[
            self._refund_line('ext-line-1', 19.84),
        ])
        refund._process()

        cn = refund.credit_note_id
        adjustment_lines = cn.invoice_line_ids.filtered(
            lambda ln: ln.product_id == adjustment_product
        )
        self.assertEqual(len(adjustment_lines), 1, 'Adjustment line should be added')
        self.assertFalse(
            adjustment_lines.tax_ids,
            'Adjustment line must be tax-free regardless of the product line taxes',
        )
        # The taxed product line keeps its tax — only the adjustment is tax-free.
        product_line = cn.invoice_line_ids.filtered(
            lambda ln: ln.product_id == self.product
        )
        self.assertTrue(product_line.tax_ids, 'Product line keeps its original tax')

    def test_adjustment_is_idempotent_on_reprocess(self):
        """Re-running _process() (dispatch retry / webhook re-delivery) must not
        append a second adjustment line — _create_credit_note short-circuits on the
        existing credit note."""
        order, _products = self._create_mismatch_order([20.0, 9.0], ['beanie', 'sugar'])
        adjustment_product = self._set_adjustment_product()

        refund = self._create_refund_record(order, total_amount=20.0, line_vals=[
            self._refund_line('beanie', 20.0),
            self._refund_line('sugar', 9.0),
        ])
        refund._process()
        refund._process()

        cn = refund.credit_note_id
        self.assertEqual(
            len(cn.invoice_line_ids.filtered(lambda ln: ln.product_id == adjustment_product)),
            1,
            'Re-processing must not duplicate the adjustment line',
        )
        self.assertAlmostEqual(cn.amount_total, 20.0, places=2)

    # --- Forced apply of a skipped refund (Apply button) ---

    def test_skipped_refund_ignored_by_automatic_dispatch(self):
        """`validate()` without the button flag leaves a skipped refund alone."""
        order, _invoice = self._create_confirmed_order_with_invoice()
        refund = self._create_refund_record(order, total_amount=19.84)
        refund.action_skip()

        result, _ids = refund.validate()

        self.assertTrue(result)
        self.assertEqual(refund.internal_status, 'skipped')
        self.assertFalse(refund.credit_note_id, 'No credit note for a skipped refund')

    def test_skipped_refund_applied_from_button(self):
        """The Apply button overrides the skip: the refund is processed and marked done."""
        order, _invoice = self._create_confirmed_order_with_invoice()
        refund = self._create_refund_record(order, total_amount=19.84)
        refund.action_skip()

        refund.action_validate()

        self.assertEqual(refund.internal_status, 'done')
        self.assertTrue(refund.credit_note_id, 'Credit note must be created')

    def test_forced_apply_keeps_placeholder_skipped(self):
        """A "refund later" placeholder re-skips itself inside _process(), so forcing
        Apply on it must not promote it to 'done' or create a credit note."""
        order, _invoice = self._create_confirmed_order_with_invoice()
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/placeholder-force',
            'erp_order_id': order.id,
            'state': 'closed',
        })
        refund = self._create_refund_record(
            order, total_amount=0, linked_return=ret, line_vals=[],
        )
        refund.validate()
        self.assertEqual(refund.internal_status, 'skipped')

        refund.action_validate()

        self.assertEqual(
            refund.internal_status, 'skipped',
            'A placeholder must stay skipped even when the merchant forces Apply',
        )
        self.assertFalse(refund.credit_note_id, 'No credit note for a placeholder refund')
