# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_refund_return_lifecycle')
class TestRefundReturnLifecycle(ReturnsRefundsAccountingTestBase):
    """Tests for lifecycle-driven processing: refunds are retried on invoice
    post + payment, returns on outgoing picking done. Also covers multi-picking
    partition (one return picking per parent fulfillment) and refund-transaction
    linkage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.return_location = cls.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.integration = cls._create_test_integration(
            'Lifecycle Test Integration',
            default_return_location_id=cls.return_location.id,
        )

        cls.product_a = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Lifecycle Shirt',
            'default_code': 'SHIRT-LC-A',
            'type': 'consu',
            'list_price': 19.84,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })
        cls.product_b = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Lifecycle Hat',
            'default_code': 'HAT-LC-B',
            'type': 'consu',
            'list_price': 25.00,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })

        # Discount product on the integration — refunds with a discount line
        # need it (resolved lazily by _adjust_credit_note_lines).
        cls.discount_product = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Lifecycle Discount',
            'default_code': 'LIFECYCLE_REFUND_DISCOUNT',
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
            'code': 'lifecycle-pm',
            'name': 'Lifecycle Payment Method',
            'payment_journal_id': cls.bank_journal.id,
        })
        cls.payment_method = cls.env['sale.order.payment.method'].create({
            'name': 'Lifecycle Payment Method',
        })
        cls.env['integration.sale.order.payment.method.mapping'].create({
            'integration_id': cls.integration.id,
            'external_payment_method_id': cls.external_payment_method.id,
            'payment_method_id': cls.payment_method.id,
        })

    def _create_order(self, lines_data):
        """Create a confirmed SO with given lines.

        lines_data: list of dicts with keys: product, qty, price, ext_id
        """
        order_lines = []
        for ld in lines_data:
            order_lines.append((0, 0, {
                'product_id': ld['product'].id,
                'product_uom_qty': ld.get('qty', 1),
                'price_unit': ld.get('price', ld['product'].list_price),
                'tax_ids': [(6, 0, ld['product'].taxes_id.ids)],
                'integration_external_id': ld['ext_id'],
            }))

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'payment_method_id': self.payment_method.id,
            'order_line': order_lines,
        })
        order.action_confirm()
        return order

    def _validate_picking(self, picking):
        """Validate a picking (set qty and button_validate).

        The class env already carries ``queue_job__no_delay=1`` (set in the
        base class), so dispatch jobs enqueued by the _action_done lifecycle
        hook run synchronously.
        """
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.with_context(
            skip_backorder=True,
            skip_sms=True,
        ).button_validate()
        self.assertEqual(picking.state, 'done')

    def _create_and_post_invoice(self, order, pay=True):
        """Create, post, and optionally pay the invoice for an order."""
        invoice = order.with_company(self.company)._create_invoices(final=True)
        invoice.with_company(self.company).action_post()
        if pay:
            self._pay_invoice(invoice)
        return invoice

    def _pay_invoice(self, invoice):
        """Pay the invoice in the order production does it: hook enqueues, work runs after.

        The class env carries ``queue_job__no_delay=1``, which would make the invoice-paid
        hook process external entities inline — nested inside Odoo's ``reconcile()``.
        Production never does that: `_enqueue_external_entities_processing` calls
        ``with_delay()``, so the work happens in its own transaction once reconciliation has
        finished.

        The difference is not cosmetic. Called from within the reconciliation post-hook,
        ``account.move._reverse_moves`` returns a credit note whose lines keep the source
        invoice's balance signs instead of being negated, so ``amount_total`` comes out
        negative and ``action_post()`` is refused. Dropping the switch for the payment keeps
        the hook firing — it still enqueues — and the processing then runs here, in the same
        order as production.
        """
        # with_context(dict) replaces the context rather than extending it.
        deferred_context = {
            key: value for key, value in self.env.context.items()
            if key != 'queue_job__no_delay'
        }
        pay_wizard = self.env['account.payment.register'].with_context(
            deferred_context,
            active_ids=invoice.ids,
            active_model='account.move',
        ).create({
            'journal_id': self.bank_journal.id,
        })
        pay_wizard._create_payments()

        # Reconciliation has finished — run what the hook enqueued.
        invoice.invoice_line_ids.mapped('sale_line_ids.order_id')._process_external_entities()

    def _create_refund_record(self, order, total_amount=19.84, currency=None):
        """Create an external.order.refund record."""
        if currency is None:
            currency = order.currency_id
        refund = self.env['external.order.refund'].create({
            'external_str_id': 'refund-test-%s' % order.id,
            'erp_order_id': order.id,
            'total_refunded_amount': total_amount,
            'currency_id': currency.id,
            'note': 'Test refund',
            'created_at_external': '2026-04-30 12:00:00',
        })
        self.env['external.order.refund.line'].create({
            'refund_id': refund.id,
            'external_line_str_id': 'ext-line-a',
            'quantity': 1,
            'restock_type': 'no_restock',
            'original_unit_price': total_amount,
            'subtotal': total_amount,
            'currency_id': currency.id,
        })
        return refund

    def _create_return_record(self, order, line_vals=None):
        """Create an external.order.return record."""
        ret = self.env['external.order.return'].create({
            'external_str_id': 'return-test-%s' % order.id,
            'erp_order_id': order.id,
            'state': 'open',
        })
        if line_vals is None:
            line_vals = [{
                'external_str_id': 'ret-line-1',
                'external_line_str_id': 'ext-line-a',
                'quantity': 1,
            }]
        for lv in line_vals:
            lv['return_id'] = ret.id
            self.env['external.order.return.line'].create(lv)
        return ret

    # -------------------------------------------------------------------------
    # Refund lifecycle: fires on invoice post + payment
    # -------------------------------------------------------------------------

    def test_refund_lifecycle_deferred_on_unpaid_retry_on_paid(self):
        """Refund defers on invoice post (unpaid → PrerequisiteNotMet), then
        succeeds when the invoice is paid. Verifies the two-phase lifecycle
        trigger: post-invoice hook (deferred, stays draft) → paid hook
        (retry, done)."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        refund = self._create_refund_record(order)

        # Sanity: refund record created but not processed at import time
        self.assertEqual(refund.internal_status, 'draft')
        self.assertFalse(refund.credit_note_id)
        self.assertFalse(refund.payment_ids)

        # Post invoice (triggers refund attempt — deferred, not failed)
        invoice = self._create_and_post_invoice(order, pay=False)

        # Refund should have been attempted and deferred: the unpaid-invoice
        # guard raises PrerequisiteNotMet (soft fail), so the record stays
        # in 'draft', not 'failed'.
        refund.invalidate_recordset()
        self.assertEqual(
            refund.internal_status, 'draft',
            'Refund should stay draft (deferred) when invoice is unpaid',
        )
        self.assertIn('E514', refund.internal_info or '')

        # Now pay the invoice (triggers retry via lifecycle hook).
        self._pay_invoice(invoice)

        # Refund should now be processed
        refund.invalidate_recordset()
        self.assertEqual(
            refund.internal_status, 'done',
            'Refund should succeed after invoice is paid',
        )
        self.assertTrue(refund.credit_note_id, 'Credit note should be created')
        self.assertTrue(refund.payment_ids, 'Refund payment should be created')

    def test_credit_note_uses_external_date(self):
        """Credit note date uses created_at_external from the refund record,
        not today's date — so historical imports reflect when the refund
        actually occurred on the platform."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        refund = self._create_refund_record(order)
        self._create_and_post_invoice(order, pay=True)

        # Refund should have been processed via lifecycle hook
        refund.invalidate_recordset()
        self.assertEqual(refund.internal_status, 'done')
        self.assertTrue(refund.credit_note_id)

        # Check credit note date matches external date
        from datetime import date
        expected_date = date(2026, 4, 30)
        self.assertEqual(
            refund.credit_note_id.date, expected_date,
            'Credit note date should match created_at_external',
        )

    # -------------------------------------------------------------------------
    # Return lifecycle: fires on outgoing picking done
    # -------------------------------------------------------------------------

    def test_return_processed_on_outgoing_picking_done(self):
        """Production sequence: customer places an order, merchant ships
        (outgoing picking validated) — only AFTER the goods are gone does
        the customer initiate a return, which arrives as an open
        external.order.return. The dispatch fires (here directly; in
        production via the returns webhook handler) and the open return is
        processed into a return picking.

        The reverse sequence (return record exists BEFORE picking
        validation) is intentionally blocked by the pre-fulfillment safety net —
        validating delivery on an order with pending returns risks
        over-shipment. test_pending_returns_safety_net.py covers that
        block; this test stays focused on the lifecycle hook for the
        post-ship flow.
        """
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])

        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self.assertEqual(len(outgoing), 1)
        self._validate_picking(outgoing)

        # Now the return arrives, after shipping.
        ret = self._create_return_record(order)
        self.assertEqual(ret.internal_status, 'draft')
        self.assertFalse(ret.picking_ids)

        # Fire the dispatch (real path: the returns webhook handler
        # enqueues this; the queue_job__no_delay context on the class env
        # makes it run synchronously here).
        order._enqueue_external_entities_processing()

        ret.invalidate_recordset()
        self.assertEqual(
            ret.internal_status, 'done',
            'Return should be processed once the outgoing picking is '
            'already done and the dispatch runs',
        )
        return_pickings = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state != 'cancel'
        )
        self.assertTrue(return_pickings, 'Return picking should be created')

    # -------------------------------------------------------------------------
    # Multi-picking partition + single-picking fallback
    # -------------------------------------------------------------------------

    def test_multi_fulfillment_return_creates_two_pickings(self):
        """Return with lines referencing different fulfillments creates one
        return picking per fulfillment group."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
            {'product': self.product_b, 'ext_id': 'ext-line-b'},
        ])

        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self.assertEqual(len(outgoing), 1)

        # Validate the single outgoing picking (contains both products)
        self._validate_picking(outgoing)

        # Create two fulfillment records pointing to the same picking
        # (simulating two Shopify fulfillments resolved to one Odoo picking)
        self.env['external.order.fulfillment'].create({
            'external_str_id': 'fulfill-a',
            'erp_order_id': order.id,
            'external_status': 'success',
            'state': 'success',
            'picking_id': outgoing.id,
        })
        self.env['external.order.fulfillment'].create({
            'external_str_id': 'fulfill-b',
            'erp_order_id': order.id,
            'external_status': 'success',
            'state': 'success',
            'picking_id': outgoing.id,
        })

        # Create return with lines referencing different fulfillments
        ret = self._create_return_record(order, line_vals=[
            {
                'external_str_id': 'ret-line-a',
                'external_line_str_id': 'ext-line-a',
                'quantity': 1,
                'external_fulfillment_str_id': 'fulfill-a',
            },
            {
                'external_str_id': 'ret-line-b',
                'external_line_str_id': 'ext-line-b',
                'quantity': 1,
                'external_fulfillment_str_id': 'fulfill-b',
            },
        ])

        ret._process()

        return_pickings = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state != 'cancel'
        )
        self.assertEqual(
            len(return_pickings), 2,
            'Should create two return pickings for two fulfillment groups',
        )

    def test_legacy_single_picking_fallback(self):
        """Return lines without external_fulfillment_str_id fall back to the
        single-picking flow — for connectors that don't supply fulfillment
        identifiers per return line."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])

        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self._validate_picking(outgoing)

        # Return line without external_fulfillment_str_id
        ret = self._create_return_record(order, line_vals=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-a',
            'quantity': 1,
            # No external_fulfillment_str_id — single-picking fallback path.
        }])
        ret._process()

        return_pickings = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state != 'cancel'
        )
        self.assertEqual(
            len(return_pickings), 1,
            'Legacy fallback should create one return picking',
        )

    # -------------------------------------------------------------------------
    # Refund transaction linkage
    # -------------------------------------------------------------------------

    def test_refund_transactions_marked_done_after_payment(self):
        """Linked refund transactions (kind=REFUND) are marked done and
        linked to payments after _register_refund_payment succeeds."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        refund = self._create_refund_record(order)

        # Create a refund transaction linked to the refund
        txn = self.env['external.order.transaction'].create({
            'name': 'TX-REFUND-DONE',
            'erp_order_id': order.id,
            'external_str_id': 'ext-txn-refund-1',
            'external_status': 'success',
            'kind': 'refund',
            'amount': '19.84',
            'currency': order.currency_id.name,
            'external_refund_id': refund.id,
        })
        self.assertEqual(
            txn.internal_status, 'draft',
            'Transaction should start as draft',
        )

        # Post and pay the invoice to trigger refund processing
        self._create_and_post_invoice(order, pay=True)

        # Refund should be processed
        refund.invalidate_recordset()
        txn.invalidate_recordset()
        self.assertEqual(
            refund.internal_status, 'done',
            'Refund should be processed',
        )
        self.assertTrue(
            refund.payment_ids,
            'Refund payments should be created',
        )

        # Transaction should be marked done with payment linked
        self.assertTrue(
            txn.is_done,
            'Linked refund transaction should be marked done',
        )
        self.assertTrue(
            txn.payment_ids,
            'Linked refund transaction should have payment_ids set',
        )

    # -------------------------------------------------------------------------
    # Late-arriving records — processing job closes the gap
    # -------------------------------------------------------------------------

    def test_late_refund_processed_via_processing_job(self):
        """Refund record created AFTER the invoice is already paid: the
        invoice-paid lifecycle hook already fired and won't fire again.
        The processing job enqueued from _apply_values_from_external must
        still pick the refund up."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])

        # 1. Full lifecycle BEFORE any refund exists
        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self._validate_picking(outgoing)
        self._create_and_post_invoice(order, pay=True)

        # Sanity: no refund record yet
        self.assertFalse(order.external_refund_ids)

        # 2. Simulate late-arriving refund via _apply_values_from_external
        #    (this is the path a webhook or pipeline re-run would take)
        refund_data = {
            'order_refunds': [{
                'external_str_id': 'late-refund-d33',
                'total_refunded_amount': 19.84,
                'currency_code': order.currency_id.name,
                'note': 'Late-arriving refund test',
                'created_at_external': '2026-05-01T10:00:00Z',
                'lines': [{
                    'external_line_str_id': 'ext-line-a',
                    'quantity': 1,
                    'restock_type': 'no_restock',
                    'original_unit_price': 19.84,
                    'subtotal': 19.84,
                    'currency_code': order.currency_id.name,
                }],
            }],
        }
        order._apply_values_from_external(refund_data)

        # 3. Refund record should exist
        order.invalidate_recordset()
        refund = order.external_refund_ids.filtered(
            lambda r: r.external_str_id == 'late-refund-d33'
        )
        self.assertTrue(refund, 'Refund record should be created')

        # 4. In queue_job__no_delay mode (set on the class env), the job
        #    runs synchronously. The refund should be processed.
        refund.invalidate_recordset()
        self.assertEqual(
            refund.internal_status, 'done',
            'Late-arriving refund should be processed via the processing job',
        )
        self.assertTrue(
            refund.credit_note_id,
            'Credit note should be created for late-arriving refund',
        )
        self.assertTrue(
            refund.payment_ids,
            'Refund payment should be created for late-arriving refund',
        )

    def test_late_return_processed_via_processing_job(self):
        """Return record created AFTER the outgoing picking is already done:
        the picking-done lifecycle hook already fired. The processing job
        enqueued from _apply_values_from_external must still pick the return
        up."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])

        # Full lifecycle BEFORE any return exists
        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self._validate_picking(outgoing)

        # Simulate late-arriving return
        return_data = {
            'order_returns': [{
                'external_str_id': 'late-return-d33',
                'state': 'open',
                'lines': [{
                    'external_str_id': 'ret-line-d33',
                    'external_line_str_id': 'ext-line-a',
                    'quantity': 1,
                }],
            }],
        }
        order._apply_values_from_external(return_data)

        order.invalidate_recordset()
        ret = order.external_return_ids.filtered(
            lambda r: r.external_str_id == 'late-return-d33'
        )
        self.assertTrue(ret, 'Return record should be created')

        ret.invalidate_recordset()
        self.assertEqual(
            ret.internal_status, 'done',
            'Late-arriving return should be processed via the processing job',
        )
        return_pickings = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state != 'cancel'
        )
        self.assertTrue(
            return_pickings,
            'Return picking should be created for late-arriving return',
        )

    # -------------------------------------------------------------------------
    # Soft fail (PrerequisiteNotMet) vs hard fail via _validate
    # -------------------------------------------------------------------------

    def test_soft_fail_keeps_record_in_draft(self):
        """PrerequisiteNotMet (e.g. no invoice) keeps the record in 'draft'
        status, not 'failed'. The processing job does NOT raise for soft
        fails — only hard failures raise."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        # No invoice — refund will defer via PrerequisiteNotMet.

        refund = self._create_refund_record(order)
        result, _ = refund.validate()

        self.assertFalse(result, 'validate() should return False')
        self.assertEqual(
            refund.internal_status, 'draft',
            'Record should stay in draft (not failed) after soft fail',
        )
        self.assertIn('E503', refund.internal_info or '')

    def test_hard_fail_marks_record_as_failed(self):
        """UserError (e.g. currency mismatch) marks the record as 'failed'
        and is propagated as a job failure for the user to act on."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        self._create_and_post_invoice(order, pay=True)

        # Create refund with mismatched currency
        other_currency = self.env.ref('base.EUR')
        other_currency.active = True
        if other_currency == order.currency_id:
            other_currency = self.env.ref('base.GBP')
            other_currency.active = True

        refund = self._create_refund_record(
            order, total_amount=19.84, currency=other_currency,
        )
        result, _ = refund.validate()

        self.assertFalse(result, 'validate() should return False')
        self.assertEqual(
            refund.internal_status, 'failed',
            'Record should be marked failed after hard fail',
        )
        self.assertIn('E506', refund.internal_info or '')

    # -------------------------------------------------------------------------
    # Processing summary aggregation
    # -------------------------------------------------------------------------

    def test_processing_summary_with_mixed_results(self):
        """The processing job aggregates results from all entity types.
        Verify the summary format with mixed pending + failed."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        # No invoice — refund will be deferred (PrerequisiteNotMet)
        self._create_refund_record(order)

        # Run processing directly (not via job)
        summary = order._process_external_entities()

        self.assertFalse(
            summary['has_failures'],
            'Soft fail should not count as failure',
        )
        self.assertEqual(summary['total_pending'], 1)
        self.assertEqual(summary['total_failed'], 0)
        self.assertIn('Waiting', summary['summary'])
        self.assertIn('E503', summary['summary'])

    def test_processing_summary_reports_placeholder_as_no_action(self):
        """A "refund later" placeholder must read clearly in the job summary:
        counted as 'recorded, no action needed' with the explanation, NOT as a
        completed item and NOT as a failure. Regression for the misleading
        'Refunds: 1 of 1 completed' a non-technical user reads as a bug."""
        order = self._create_order([
            {'product': self.product_a, 'ext_id': 'ext-line-a'},
        ])
        self._create_and_post_invoice(order, pay=True)

        # Placeholder refund: zero amount + a linked return. Mark the return done
        # so only the placeholder refund drives the summary in this test.
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/ph-1',
            'erp_order_id': order.id,
            'state': 'open',
        })
        ret.mark_done()
        refund = self.env['external.order.refund'].create({
            'external_str_id': 'gid://shopify/Refund/ph-1',
            'erp_order_id': order.id,
            'total_refunded_amount': 0.0,
            'currency_id': order.currency_id.id,
            'linked_return_str_id': 'gid://shopify/Return/ph-1',
            'linked_return_id': ret.id,
        })

        summary = order._process_external_entities()

        refund.invalidate_recordset()
        self.assertEqual(refund.internal_status, 'skipped')
        self.assertFalse(summary['has_failures'])
        self.assertEqual(summary['total_failed'], 0)
        self.assertEqual(summary['total_skipped'], 1)
        self.assertIn('no action needed', summary['summary'])
        # The plain-language explanation reaches the job log.
        self.assertIn('refund later', summary['summary'])
        # The misleading "completed" count must not appear for a placeholder-only
        # refund.
        self.assertNotIn('1 of 1 completed', summary['summary'])

    # -------------------------------------------------------------------------
    # Legacy refund-driven restock — synthesized return drives the full
    # pipeline (credit note + restock picking) just like a real return
    # -------------------------------------------------------------------------

    def test_end_to_end_refund_creates_return_picking(self):
        """A refund with restockType=RETURN and no platform Return entity is
        modelled (by the connector parser) as a refund + a synthesized return
        sharing 'refund-<gid>'. End-to-end, processing must create BOTH a credit
        note (refund side) and a restock picking (return side), and validating
        the return picking must drop qty_delivered.

        This is the production shape for Shopify order #1674 (3 beanies ordered,
        2 refunded with restock). The connector emits the records; this test
        verifies the downstream core pipeline handles the synthetic return
        identically to a real one.
        """
        refund_gid = 'gid://shopify/Refund/950343270614'
        synthetic_return_id = 'refund-%s' % refund_gid

        order = self._create_order([
            {'product': self.product_a, 'qty': 3, 'ext_id': 'ext-line-a'},
        ])
        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self._validate_picking(outgoing)
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 3.0)

        # Invoice must be paid before the refund can build its credit note.
        self._create_and_post_invoice(order, pay=True)

        # Synthesized return (what the parser appends to order_returns). Shopify's
        # restock means the goods are already back in stock, so restocked_externally
        # is set — the return picking is validated immediately on creation.
        ret = self.env['external.order.return'].create({
            'external_str_id': synthetic_return_id,
            'erp_order_id': order.id,
            'state': 'open',
            'restocked_externally': True,
        })
        self.env['external.order.return.line'].create({
            'return_id': ret.id,
            'external_str_id': '%s/ext-line-a' % synthetic_return_id,
            'external_line_str_id': 'ext-line-a',
            'quantity': 2,
            'external_sku': 'woo-beanie',
        })
        # Paired refund, linked to the synthetic return (linked_return_id is
        # what ingestion resolves from linked_return_str_id — set directly here).
        refund = self.env['external.order.refund'].create({
            'external_str_id': refund_gid,
            'erp_order_id': order.id,
            'total_refunded_amount': 2 * 19.84,
            'currency_id': order.currency_id.id,
            'note': 'Customer requested refund',
            'created_at_external': '2026-06-14 13:29:20',
            'linked_return_str_id': synthetic_return_id,
            'linked_return_id': ret.id,
        })
        self.env['external.order.refund.line'].create({
            'refund_id': refund.id,
            'external_line_str_id': 'ext-line-a',
            'quantity': 2,
            'restock_type': 'return',
            'original_unit_price': 19.84,
            'subtotal': 2 * 19.84,
            'currency_id': order.currency_id.id,
        })

        order._process_external_entities()

        # Refund side: credit note + payment created, record done.
        refund.invalidate_recordset()
        self.assertTrue(refund.is_done, 'Refund should be processed')
        self.assertTrue(refund.credit_note_id, 'Credit note must be created')
        self.assertTrue(refund.payment_ids, 'Refund payment must be created')

        # Return side: one restock picking for 2 units, record done.
        ret.invalidate_recordset()
        self.assertTrue(ret.is_done, 'Synthetic return should be processed')
        return_picking = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
        )
        self.assertEqual(len(return_picking), 1, 'One restock picking expected')
        self.assertEqual(
            sum(return_picking.move_ids.mapped('product_uom_qty')), 2.0,
            'Restock picking must move the 2 returned units',
        )

        # Restock = goods already received → the picking is validated immediately
        # (no manual step), and qty_delivered drops from 3 to 1 right away.
        return_picking.invalidate_recordset(['state'])
        self.assertEqual(
            return_picking.state, 'done',
            'Restock picking must be auto-validated on creation',
        )
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(
            order.order_line.qty_delivered, 1.0,
            'qty_delivered must drop from 3 to 1 once the restock is received',
        )
