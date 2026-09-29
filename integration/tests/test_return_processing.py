# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..exceptions import PrerequisiteNotMet
from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_return_processing')
class TestReturnProcessing(ReturnsRefundsAccountingTestBase):
    """Tests for external.order.return._process() — return picking creation,
    cancellation, product resolution, and fail-loud error guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.return_location = cls.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.integration = cls._create_test_integration(
            'Return Processing Test Integration',
            default_return_location_id=cls.return_location.id,
        )

        cls.product = cls.env['product.product'].with_company(
            cls.company,
        ).create({
            'name': 'Return Processing T-Shirt',
            'default_code': 'TSHIRT-RP-001',
            'type': 'consu',
            'list_price': 19.84,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })

    def _create_order_with_validated_delivery(
        self, product=None, qty=1, external_line_id='ext-line-1',
    ):
        """Helper: create a confirmed SO with a validated outgoing picking."""
        if product is None:
            product = self.product

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': product.list_price,
                'tax_ids': [(6, 0, product.taxes_id.ids)],
                'integration_external_id': external_line_id,
            })],
        })
        order.action_confirm()

        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self.assertEqual(len(picking), 1, 'Expected exactly one outgoing picking')

        # Set quantities and validate
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.with_context(
            skip_backorder=True,
            skip_sms=True,
        ).button_validate()
        self.assertEqual(
            picking.state, 'done',
            'Delivery picking must be done after validation',
        )

        return order, picking

    def _create_return_record(self, order, state='open', line_vals=None):
        """Helper: create an external.order.return record."""
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/test-%s' % order.id,
            'erp_order_id': order.id,
            'state': state,
        })

        if line_vals is None:
            line_vals = [{
                'return_id': ret.id,
                'external_str_id': 'ret-line-1',
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
            }]

        for lv in line_vals:
            lv['return_id'] = ret.id
            self.env['external.order.return.line'].create(lv)

        return ret

    # --- Happy path ---

    def test_open_return_creates_return_picking(self):
        """Open return creates a return picking with correct destination,
        product, and quantity. Uses a non-default external_line_id to verify
        product resolution via external_line_str_id (no SKU fallback)."""
        order, _picking = self._create_order_with_validated_delivery(
            external_line_id='ext-abc-product-resolution',
        )

        ret = self._create_return_record(order, line_vals=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-abc-product-resolution',
            'quantity': 1,
        }])
        ret._process()

        self.assertTrue(ret.picking_ids, 'Return picking should be created')
        return_picking = ret.picking_ids[0]
        # Odoo 18 wizard confirms+assigns the picking after creation
        self.assertIn(
            return_picking.state, ('confirmed', 'assigned', 'waiting'),
            'Return picking should be confirmed/assigned by wizard',
        )
        self.assertEqual(
            return_picking.location_dest_id, self.return_location,
            'Return picking destination should be the configured return location',
        )

        # Check product resolution and quantity on the picking moves
        return_moves = return_picking.move_ids
        self.assertEqual(len(return_moves), 1, 'Should have one return move')
        self.assertEqual(
            return_moves[0].product_id, self.product,
            'Return move should reference correct product via external_line_str_id',
        )

    def test_partial_return_quantity_matches_return_line(self):
        """Partial return: order had qty=3, return is for qty=1. The
        stock.return.picking wizard defaults to full quantity; we must
        override with the return-specific quantity."""
        order, _picking = self._create_order_with_validated_delivery(qty=3)

        ret = self._create_return_record(order, line_vals=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
        }])
        ret._process()

        return_picking = ret.picking_ids[0]
        return_move = return_picking.move_ids[0]
        self.assertEqual(
            return_move.product_uom_qty, 1,
            'Return move qty should be 1, not 3',
        )

    # --- Restock location guard ---

    def test_no_return_location_raises_4(self):
        """Missing default_return_location_id fails-loud with an actionable
        message pointing to the Returns & Refunds tab."""
        order, _picking = self._create_order_with_validated_delivery()

        original_location = self.integration.default_return_location_id
        self.integration.write({'default_return_location_id': False})
        self.addCleanup(
            self.integration.write,
            {'default_return_location_id': original_location.id},
        )

        ret = self._create_return_record(order)

        with self.assertRaises(UserError) as cm:
            ret._process()
        self.assertIn('E505', cm.exception.args[0])

    # --- Delivery prerequisite guard ---

    def test_no_done_outgoing_picking_raises_16(self):
        """Return on an order without a validated delivery picking soft-fails
        via PrerequisiteNotMet. Retried by the lifecycle hook when the
        outgoing picking is validated."""
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
        # Do NOT validate the delivery picking

        ret = self._create_return_record(order)

        with self.assertRaises(PrerequisiteNotMet) as cm:
            ret._process()
        self.assertIn('E516', str(cm.exception))

    # --- Cancellation handling ---

    def test_canceled_state_cancels_picking(self):
        """Cancel a return after picking created: the non-done return
        picking should be canceled."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, state='open')
        ret._process()
        return_picking = ret.picking_ids[0]
        self.assertNotEqual(
            return_picking.state, 'cancel',
            'Return picking should not be canceled yet',
        )

        # Now simulate cancel
        ret.write({'state': 'canceled', 'internal_status': 'draft'})
        ret._process()

        self.assertEqual(
            return_picking.state, 'cancel',
            'Return picking should be canceled after return cancel',
        )

    def test_declined_state_cancels_picking(self):
        """`declined` shares the cancel/decline branch with `canceled`. Both
        states must cancel any pending return picking; only the trigger differs
        (`canceled` = customer-driven, `declined` = merchant-driven)."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, state='open')
        ret._process()
        return_picking = ret.picking_ids[0]
        self.assertNotEqual(return_picking.state, 'cancel')

        ret.write({'state': 'declined', 'internal_status': 'draft'})
        ret._process()

        self.assertEqual(
            return_picking.state, 'cancel',
            'Return picking should be canceled after return is declined',
        )

    def test_cancel_after_picking_validated_raises_11(self):
        """Canceling a return after the return picking is validated (done)
        fails-loud — physical goods were already received and the user must
        reverse that manually."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, state='open')
        ret._process()
        return_picking = ret.picking_ids[0]

        # Force-validate the return picking to simulate warehouse receipt
        for move in return_picking.move_ids:
            move.quantity = move.product_uom_qty
        return_picking.with_context(
            skip_backorder=True,
            skip_sms=True,
        ).button_validate()
        self.assertEqual(
            return_picking.state, 'done',
            'Test setup: return picking must be done',
        )

        # Now try to cancel
        ret.write({'state': 'canceled', 'internal_status': 'draft'})

        with self.assertRaises(UserError) as cm:
            ret._process()
        self.assertIn('E511', cm.exception.args[0])

    # --- to_refund flag lifecycle ---

    def test_return_validation_decreases_so_delivered_qty(self):
        """to_refund=True on return picking lines causes qty_delivered to
        decrease when the return picking is validated. qty_delivered tracks
        physical movement independently from qty_invoiced (financial)."""
        order, _outgoing = self._create_order_with_validated_delivery(qty=2)
        so_line = order.order_line[0]
        self.assertEqual(
            so_line.qty_delivered, 2.0,
            'Sanity: original delivery should be 2 units',
        )

        ret = self._create_return_record(order, line_vals=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
        }])
        ret._process()

        return_picking = ret.picking_ids
        self.assertEqual(
            len(return_picking), 1,
            'Exactly one return picking should exist',
        )

        # qty_delivered unchanged after creation (Odoo updates on validation)
        so_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(
            so_line.qty_delivered, 2.0,
            'qty_delivered should not change on return picking creation',
        )

        # Validate the return picking (warehouse user receives the goods)
        for move in return_picking.move_ids:
            move.quantity = move.product_uom_qty
        return_picking.with_context(
            skip_backorder=True,
            skip_sms=True,
        ).button_validate()
        self.assertEqual(
            return_picking.state, 'done',
            'Return picking must be done after validation',
        )

        # KEY ASSERTION: qty_delivered decreases after validation
        so_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(
            so_line.qty_delivered, 1.0,
            'qty_delivered must decrease from 2 to 1 after validating '
            'return of 1 unit (to_refund=True propagates from wizard to move)',
        )

    # --- Product resolution guard ---

    def test_unresolvable_return_line_raises_17(self):
        """Return line with no matching SO line (no integration_external_id
        match) fails-loud."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, line_vals=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-XYZ-NONEXISTENT',
            'quantity': 1,
        }])

        with self.assertRaises(UserError) as cm:
            ret._process()
        self.assertIn('E517', cm.exception.args[0])

    # --- Idempotency ---

    def test_reprocessing_open_return_does_not_duplicate_picking(self):
        """_create_return_picking() short-circuits when a non-canceled return
        picking already exists on the record. Re-running _process() on an
        already-processed open return must not create a second picking
        (matters for the dispatch-retry safety net)."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, state='open')
        ret._process()
        self.assertEqual(
            len(ret.picking_ids), 1,
            'First _process() should create exactly one return picking',
        )
        first_picking_id = ret.picking_ids.id

        ret._process()

        self.assertEqual(
            len(ret.picking_ids), 1,
            'Second _process() must not create a duplicate picking',
        )
        self.assertEqual(
            ret.picking_ids.id, first_picking_id,
            'The original picking record should be retained',
        )

    # --- Closed-state ingestion (D-41 regression) ---

    def test_closed_return_creates_picking(self):
        """A return that arrives already in 'closed' state (historical import,
        or platform opened and closed it between webhook deliveries) must create
        a return transfer AND validate it — 'closed' means the goods are
        physically back. Regression guard for D-41 (transfer created) extended by
        D-60 (transfer validated)."""
        order, _picking = self._create_order_with_validated_delivery()

        ret = self._create_return_record(order, state='closed')
        ret._process()

        return_pickings = ret.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state != 'cancel'
        )
        self.assertEqual(
            len(return_pickings), 1,
            'Closed return must create exactly one return picking',
        )
        self.assertEqual(
            return_pickings.state, 'done',
            'Closed return validates its transfer (goods received)',
        )
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 0.0)

    # --- Re-open on platform state change after processing (D-60) ---

    def test_reopen_on_close_validates_existing_transfer(self):
        """A return imported as Open creates a Ready transfer and is marked done.
        When the platform later closes it ("Process and refund"), writing the new
        state re-opens the record (write() hook), and reprocessing validates the
        EXISTING transfer (goods received) — not a new one."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order)
        ret.validate()
        self.assertEqual(ret.internal_status, 'done')
        picking = ret.picking_ids
        self.assertEqual(len(picking), 1)
        self.assertIn(picking.state, ('assigned', 'confirmed', 'waiting'))

        # Platform closes the return — the incoming-state write re-opens it.
        ret.write({'state': 'closed'})
        self.assertEqual(
            ret.internal_status, 'draft',
            'closed-after-done return must re-open for reprocessing',
        )

        ret.validate()
        self.assertEqual(ret.internal_status, 'done')
        picking.invalidate_recordset(['state'])
        self.assertEqual(
            picking.state, 'done',
            'Existing transfer must be validated on close, not recreated',
        )
        self.assertEqual(ret.picking_ids, picking, 'No duplicate transfer created')
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 0.0)

    def test_reopen_on_cancel_cancels_existing_transfer(self):
        """A return imported as Open (Ready transfer, done). When the platform
        cancels it, the write() hook re-opens the record and reprocessing cancels
        the EXISTING Ready transfer."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order)
        ret.validate()
        picking = ret.picking_ids
        self.assertIn(picking.state, ('assigned', 'confirmed', 'waiting'))

        ret.write({'state': 'canceled'})
        self.assertEqual(ret.internal_status, 'draft')

        ret.validate()
        picking.invalidate_recordset(['state'])
        self.assertEqual(
            picking.state, 'cancel',
            'Existing Ready transfer must be canceled when the return is canceled',
        )

    def test_refetch_same_state_does_not_reopen(self):
        """A webhook that re-fetches the order without a state change must NOT
        re-open a processed return (no churn, no re-validation)."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order)
        ret.validate()
        self.assertEqual(ret.internal_status, 'done')

        # Same state written again (e.g. a returns/update webhook with no change).
        ret.write({'state': 'open'})
        self.assertEqual(
            ret.internal_status, 'done',
            'Unchanged state must not re-open the record',
        )

    def test_reopen_then_cancel_after_validated_raises_11(self):
        """If a return was already validated (goods received) and the platform
        then cancels it, re-opening and reprocessing must fail loud (E511) — the
        goods are physically here and cannot be auto-uncanceled."""
        order, _picking = self._create_order_with_validated_delivery()
        # Closed on arrival → transfer validated (done).
        ret = self._create_return_record(order, state='closed')
        ret.validate()
        self.assertEqual(ret.picking_ids.state, 'done')

        ret.write({'state': 'canceled'})
        self.assertEqual(ret.internal_status, 'draft')

        result, _ids = ret.validate()
        self.assertFalse(result)
        self.assertEqual(ret.internal_status, 'failed')
        self.assertIn('E511', ret.internal_info or '')

    # --- Forced apply of a skipped return (Apply button) ---

    def test_skipped_return_ignored_by_automatic_dispatch(self):
        """`validate()` without the button flag leaves a skipped return alone."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order)
        ret.action_skip()

        result, _ids = ret.validate()

        self.assertTrue(result)
        self.assertEqual(ret.internal_status, 'skipped')
        self.assertFalse(ret.picking_ids, 'No transfer may be created for a skipped return')

    def test_skipped_return_applied_from_button(self):
        """The Apply button overrides the skip: the return is processed and marked done."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order)
        ret.action_skip()

        ret.action_validate()

        self.assertEqual(ret.internal_status, 'done')
        self.assertEqual(len(ret.picking_ids), 1, 'Return transfer must be created')

    def test_forced_apply_soft_fail_restores_skip(self):
        """A forced apply that cannot proceed yet (no done delivery, E516) must leave the
        record skipped — 'draft' would re-block the outgoing picking the skip unblocked."""
        # No validated delivery here, so no taxes either: E516 fires before any accounting,
        # and leaving the tax key out keeps the fixture identical across version branches.
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': self.product.list_price,
                'integration_external_id': 'ext-line-1',
            })],
        })
        order.action_confirm()

        ret = self._create_return_record(order)
        ret.action_skip()

        ret.action_validate()

        self.assertEqual(ret.internal_status, 'skipped')
        self.assertIn('E516', ret.internal_info or '')
        order.invalidate_recordset(['has_pending_external_returns'])
        self.assertFalse(
            order.has_pending_external_returns,
            'A failed forced apply must not put the return back into the pending set',
        )

    def test_forced_apply_hard_fail_restores_skip(self):
        """A forced apply that hard-fails keeps 'skipped' instead of 'failed': 'failed'
        records are retried on every automatic dispatch, which the skip ruled out."""
        order, _picking = self._create_order_with_validated_delivery()
        ret = self._create_return_record(order, state='closed')
        ret.validate()
        self.assertEqual(ret.picking_ids.state, 'done')

        # Platform cancels an already-received return: reprocessing fails loud (E511).
        ret.write({'state': 'canceled'})
        self.assertEqual(ret.internal_status, 'draft')
        ret.action_skip()

        ret.action_validate()

        self.assertEqual(ret.internal_status, 'skipped')
        self.assertIn('E511', ret.internal_info or '')
