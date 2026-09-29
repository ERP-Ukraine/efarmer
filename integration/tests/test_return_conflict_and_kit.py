# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_return_conflict_and_kit')
class TestReturnConflictAndKit(ReturnsRefundsAccountingTestBase):
    """Return conflict guard + kit (phantom BoM) support.

    Covers:
      - Kit return: BoM-explode the parent quantity into per-component
        wizard lines so the native return wizard accepts the request.
      - qty_delivered accounting for kits through the full lifecycle
        (settles the diagnostic-flagged uncertainty).
      - Quantity-aware conflict guard across three scenarios (no existing
        return / validated returns exist / open returns exist) with kit
        and non-kit products handled by the same code path.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.return_location = cls.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

        cls.integration = cls._create_test_integration(
            'Return Conflict & Kit Test Integration',
            default_return_location_id=cls.return_location.id,
        )

        cls.tshirt = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Conflict-Test T-Shirt',
            'default_code': 'TSHIRT-CONFLICT',
            'type': 'consu',
            'list_price': 19.84,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })

        # Kit setup: 1 Chair = 1 Seat + 1 Backrest + 4 Legs.
        cls.chair = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Kit-Test Chair',
            'default_code': 'CHAIR-KIT',
            'type': 'consu',
            'list_price': 99.0,
            'taxes_id': [(6, 0, cls.tax.ids)],
        })
        cls.seat = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Kit-Test Seat',
            'default_code': 'SEAT',
            'type': 'consu',
        })
        cls.backrest = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Kit-Test Backrest',
            'default_code': 'BACKREST',
            'type': 'consu',
        })
        cls.leg = cls.env['product.product'].with_company(cls.company).create({
            'name': 'Kit-Test Leg',
            'default_code': 'LEG',
            'type': 'consu',
        })
        cls.chair_bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.chair.product_tmpl_id.id,
            'product_id': cls.chair.id,
            'product_qty': 1.0,
            'type': 'phantom',
            'bom_line_ids': [
                (0, 0, {'product_id': cls.seat.id, 'product_qty': 1.0}),
                (0, 0, {'product_id': cls.backrest.id, 'product_qty': 1.0}),
                (0, 0, {'product_id': cls.leg.id, 'product_qty': 4.0}),
            ],
        })

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _create_order(self, product, qty=1, external_line_id='ext-line-1'):
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
        return order

    def _validate_outgoing(self, order):
        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing'
        )
        self.assertEqual(len(picking), 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.with_context(
            skip_backorder=True, skip_sms=True,
        ).button_validate()
        self.assertEqual(picking.state, 'done')
        return picking

    def _create_order_with_validated_delivery(
        self, product=None, qty=1, external_line_id='ext-line-1',
    ):
        if product is None:
            product = self.tshirt
        order = self._create_order(product, qty=qty, external_line_id=external_line_id)
        picking = self._validate_outgoing(order)
        return order, picking

    def _create_return_record(self, order, lines, state='open', external_id=None):
        ret = self.env['external.order.return'].create({
            'external_str_id': external_id or 'gid://shopify/Return/test-%s' % order.id,
            'erp_order_id': order.id,
            'state': state,
        })
        for lv in lines:
            lv['return_id'] = ret.id
            self.env['external.order.return.line'].create(lv)
        return ret

    def _validate_return_picking(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.with_context(
            skip_backorder=True, skip_sms=True,
        ).button_validate()
        self.assertEqual(picking.state, 'done')

    # -----------------------------------------------------------------------
    # Kit return: explosion + accounting
    # -----------------------------------------------------------------------

    def test_kit_return_explodes_to_components(self):
        """External return for 1 kit parent creates a return picking with
        correct per-component quantities (1 Seat + 1 Backrest + 4 Legs for
        1 Chair). Mirrors the manual kit fulfillment pattern."""
        order, outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=2, external_line_id='ext-chair',
        )
        # Sanity: the outgoing picking explodes into component moves.
        outgoing_products = outgoing.move_ids.mapped('product_id')
        self.assertIn(self.seat, outgoing_products)
        self.assertIn(self.backrest, outgoing_products)
        self.assertIn(self.leg, outgoing_products)
        self.assertNotIn(self.chair, outgoing_products)

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        ret._process()

        self.assertEqual(len(ret.picking_ids), 1)
        return_moves = ret.picking_ids.move_ids
        # One move per component (Seat, Backrest, Leg)
        self.assertEqual(len(return_moves), 3)

        qty_by_product = {m.product_id.id: m.product_uom_qty for m in return_moves}
        self.assertEqual(qty_by_product[self.seat.id], 1)
        self.assertEqual(qty_by_product[self.backrest.id], 1)
        self.assertEqual(qty_by_product[self.leg.id], 4)

        # bom_line_id is set on each return component move (preserved
        # through the wizard's move.copy()), which the conflict guard's
        # composition logic relies on.
        for mv in return_moves:
            self.assertTrue(
                mv.bom_line_id,
                '%s return move must keep bom_line_id from outgoing' % mv.product_id.name,
            )

    def test_kit_return_qty_delivered_accounting(self):
        """The diagnostic-flagged accounting test. 2-Chair order, fulfill,
        validate, process external return for 1 Chair, validate the return
        picking, assert qty_delivered drops from 2 to 1 on the kit SO line.
        Settles the one uncertainty the diagnostic could not resolve without
        running."""
        order, _outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=2, external_line_id='ext-chair',
        )
        so_line = order.order_line[0]
        self.assertEqual(so_line.product_id, self.chair)
        self.assertEqual(
            so_line.qty_delivered, 2.0,
            'sale_mrp must report qty_delivered=2 in parent units after fulfilling 2 chairs',
        )

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        ret._process()
        self.assertEqual(len(ret.picking_ids), 1)
        return_picking = ret.picking_ids

        # qty_delivered unchanged by picking creation
        so_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(so_line.qty_delivered, 2.0)

        # Validate the return picking — physically receive the components.
        self._validate_return_picking(return_picking)

        so_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(
            so_line.qty_delivered, 1.0,
            'qty_delivered must drop from 2 to 1 (parent units) after '
            'validating the return of 1 chair-kit',
        )

    # -----------------------------------------------------------------------
    # Conflict guard — Scenario 1: no existing return
    # -----------------------------------------------------------------------

    def test_conflict_no_existing_return(self):
        """Baseline: no prior return picking on the order, standard flow
        creates a return picking unchanged. Regression guard so the new
        conflict guard doesn't break the happy path."""
        order, _picking = self._create_order_with_validated_delivery(qty=2)
        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
        }])
        ret._process()
        self.assertEqual(len(ret.picking_ids), 1)

    # -----------------------------------------------------------------------
    # Conflict guard — Scenario 2: validated return picking(s) exist
    # -----------------------------------------------------------------------

    def test_conflict_validated_return_within_quota(self):
        """4 delivered, 2 already returned (validated). New external return
        for 2 → succeeds (2 + 2 = 4, within quota)."""
        order, _picking = self._create_order_with_validated_delivery(qty=4)
        first = self._create_return_record(order, external_id='ret-1', lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        first._process()
        self._validate_return_picking(first.picking_ids)

        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 2.0)

        second = self._create_return_record(order, external_id='ret-2', lines=[{
            'external_str_id': 'ret-line-2',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        second._process()
        self.assertEqual(len(second.picking_ids), 1)

    def test_conflict_validated_return_over_quota(self):
        """4 delivered, 2 already returned + validated. New external return
        for 3 → E518b (over-return; only 2 remaining)."""
        order, _picking = self._create_order_with_validated_delivery(qty=4)
        first = self._create_return_record(order, external_id='ret-1', lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        first._process()
        self._validate_return_picking(first.picking_ids)

        second = self._create_return_record(order, external_id='ret-2', lines=[{
            'external_str_id': 'ret-line-2',
            'external_line_str_id': 'ext-line-1',
            'quantity': 3,
        }])
        with self.assertRaises(UserError) as cm:
            second._process()
        self.assertIn('E518b', cm.exception.args[0])

    # -----------------------------------------------------------------------
    # Conflict guard — Scenario 3: open return picking(s) exist
    # -----------------------------------------------------------------------

    def _create_manual_return_picking(self, source_picking, product, qty):
        """Build a return picking on `source_picking` using the native Odoo
        wizard — no external record links to it. Used to simulate the
        'manually-created return picking' case the conflict guard handles.
        """
        wizard = self.env['stock.return.picking'].with_context(
            active_id=source_picking.id,
            active_model='stock.picking',
        ).create({})
        line = wizard.product_return_moves.filtered(
            lambda ln: ln.product_id.id == product.id
        )
        line[0].write({'quantity': qty, 'to_refund': True})
        new_picking = wizard._create_return()
        return new_picking

    def test_conflict_open_return_matches_manual_picking(self):
        """A manually-created (no external record) open return picking for
        qty=2 exists. External return arrives with the same composition
        (qty=2). The guard adopts the manual picking — no duplicate is
        created — and links it to the new external record."""
        order, outgoing = self._create_order_with_validated_delivery(qty=4)
        manual = self._create_manual_return_picking(outgoing, self.tshirt, 2)
        self.assertIn(manual.state, ('confirmed', 'assigned', 'waiting'))

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        ret._process()

        return_pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
        )
        self.assertEqual(
            len(return_pickings), 1,
            'Guard must adopt the existing manual picking instead of '
            'creating a duplicate.',
        )
        self.assertEqual(ret.picking_ids, manual)

    def test_conflict_open_return_mismatch_raises(self):
        """A manually-created open return picking for qty=1 exists. External
        return arrives for qty=2 (composition does not match). Guard fails
        loud with E518a — user must resolve the existing return first."""
        order, outgoing = self._create_order_with_validated_delivery(qty=4)
        self._create_manual_return_picking(outgoing, self.tshirt, 1)

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        with self.assertRaises(UserError) as cm:
            ret._process()
        self.assertIn('E518a', cm.exception.args[0])

    def test_conflict_manual_picking_composition_match(self):
        """Composition match on multi-line composition: manual picking
        covers exactly the same SO lines with the same quantities the
        incoming return requests. Guard adopts."""
        # Use a single SO line with qty=3, manual return of 2 — same as the
        # incoming external return of 2 (single-line composition).
        order, outgoing = self._create_order_with_validated_delivery(qty=3)
        manual = self._create_manual_return_picking(outgoing, self.tshirt, 2)

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 2,
        }])
        ret._process()

        self.assertEqual(ret.picking_ids, manual)
        # No second incoming picking was created.
        all_returns = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
        )
        self.assertEqual(len(all_returns), 1)

    # -----------------------------------------------------------------------
    # Kit + conflict guard interaction (Approach A — exact)
    # -----------------------------------------------------------------------

    def test_conflict_kit_validated_return_within_quota(self):
        """2-Chair order, 1 chair already returned + validated
        (qty_delivered=1). New external return for 1 chair → succeeds."""
        order, _outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=2, external_line_id='ext-chair',
        )
        first = self._create_return_record(order, external_id='ret-kit-1', lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        first._process()
        self._validate_return_picking(first.picking_ids)

        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 1.0)

        second = self._create_return_record(order, external_id='ret-kit-2', lines=[{
            'external_str_id': 'ret-line-2',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        second._process()
        self.assertEqual(len(second.picking_ids), 1)

    def test_conflict_kit_over_return_raises(self):
        """2-Chair order, 1 chair already returned + validated. New external
        return for 2 chairs → E518b (only 1 chair remaining returnable)."""
        order, _outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=2, external_line_id='ext-chair',
        )
        first = self._create_return_record(order, external_id='ret-kit-1', lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        first._process()
        self._validate_return_picking(first.picking_ids)

        second = self._create_return_record(order, external_id='ret-kit-2', lines=[{
            'external_str_id': 'ret-line-2',
            'external_line_str_id': 'ext-chair',
            'quantity': 2,
        }])
        with self.assertRaises(UserError) as cm:
            second._process()
        self.assertIn('E518b', cm.exception.args[0])

    def test_conflict_kit_open_return_blocks_second_partial(self):
        """2-Chair order, 1 chair return is OPEN (not yet validated). A new
        external return for 1 chair arrives — different external record,
        different composition (e.g. different reason, different webhook).
        Since 1 chair worth of components is already reserved as open, the
        kit composition matches by parent-unit count and the guard adopts
        the existing picking rather than creating a duplicate. Validates
        Approach A: kit composition comparison works in parent units."""
        order, _outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=2, external_line_id='ext-chair',
        )
        first = self._create_return_record(order, external_id='ret-kit-1', lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        first._process()
        first_picking = first.picking_ids

        # A second external return arrives for the same composition.
        second = self._create_return_record(order, external_id='ret-kit-2', lines=[{
            'external_str_id': 'ret-line-2',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])
        second._process()

        self.assertEqual(
            second.picking_ids, first_picking,
            'Second external return should adopt the existing open kit '
            'return picking (composition match in parent units).',
        )
        # Still exactly one return picking on the order.
        all_returns = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
        )
        self.assertEqual(len(all_returns), 1)

    # -----------------------------------------------------------------------
    # Kit BoM mutated after shipping — partial component match must raise
    # -----------------------------------------------------------------------

    def test_kit_partial_component_match_raises_e518c(self):
        """When the kit BoM is edited between shipping and return (e.g. legs
        removed), the explode result references components that are no longer
        present on the outgoing picking. Previously: ``matched_any`` flipped
        True on the first matching component (seat + backrest) and the return
        picking was created with a structurally short composition.

        After the fix: any unmatched component raises E518c; the merchant is
        told which components are missing.
        """
        order, outgoing = self._create_order_with_validated_delivery(
            product=self.chair, qty=1, external_line_id='ext-chair',
        )

        # Sanity: the outgoing picking has 3 component moves at shipping time.
        outgoing_products = set(outgoing.move_ids.mapped('product_id'))
        self.assertEqual(outgoing_products, {self.seat, self.backrest, self.leg})

        # Now mutate the BoM AFTER shipping — drop the legs. The next return
        # explode will reference seat + backrest only and miss the legs
        # on the picking... wait, the opposite: we need explode to produce a
        # component the picking DOESN'T have. Add a new component to the BoM.
        decoration = self.env['product.product'].with_company(self.company).create({
            'name': 'Kit-Test Decoration',
            'default_code': 'DECORATION',
            'type': 'consu',
        })
        self.env['mrp.bom.line'].create({
            'bom_id': self.chair_bom.id,
            'product_id': decoration.id,
            'product_qty': 1.0,
        })

        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-chair',
            'quantity': 1,
        }])

        with self.assertRaises(UserError) as cm:
            ret._process()

        self.assertIn('E518c', cm.exception.args[0])
        # The error must name the missing component so the merchant can act.
        self.assertIn('Decoration', cm.exception.args[0])
        # No structurally-short return picking was created.
        self.assertFalse(ret.picking_ids)

    # -----------------------------------------------------------------------
    # Manual return with to_refund=False — must still count toward the quota
    # -----------------------------------------------------------------------

    def test_manual_return_without_to_refund_counts_in_quota(self):
        """A warehouse user receives goods back from the customer via a
        manual picking and unticks "to refund" in the wizard. The
        external-return guard must still see those moves when calculating
        remaining returnable quantity — otherwise an external return that
        plus the manual one would overshoot delivered passes the over-return
        check (E518b) and produces a duplicate picking, or worse, negative
        wizard quantities.
        """
        order, outgoing = self._create_order_with_validated_delivery(qty=4)

        # Manual return picking, 2 units, to_refund=False.
        wizard = self.env['stock.return.picking'].with_context(
            active_id=outgoing.id,
            active_model='stock.picking',
        ).create({})
        line = wizard.product_return_moves.filtered(
            lambda ln: ln.product_id.id == self.tshirt.id
        )
        line[0].write({'quantity': 2, 'to_refund': False})
        manual = wizard._create_return()
        # Defensive: confirm the move actually carries to_refund=False so we
        # are testing what we think we are.
        self.assertTrue(
            all(not m.to_refund for m in manual.move_ids),
            'Manual picking moves must have to_refund=False',
        )

        # External return arrives for 3 more units (delivered=4, manual=2,
        # this=3 → 2+3=5 > 4 → over-return).
        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 3,
        }])

        with self.assertRaises(UserError) as cm:
            ret._process()
        self.assertIn('E518b', cm.exception.args[0])

    # -----------------------------------------------------------------------
    # Synthetic return (legacy refund-driven restock) + real return coexist
    # -----------------------------------------------------------------------

    def test_synthetic_then_real_return_quota(self):
        """Order delivered 3 units. A refund with restock=RETURN synthesizes a
        return for 2 units (external_str_id prefixed 'refund-') whose restock
        picking is created and validated (qty_delivered → 1). A separate REAL
        Return event then arrives for the remaining 1 unit. The conflict guard
        must allow it (2 + 1 = 3 = delivered): synthetic and real returns are
        evaluated by quantity, not by id format. This is the load-bearing proof
        that the synthesized return integrates cleanly with the conflict guard.
        """
        order, _picking = self._create_order_with_validated_delivery(qty=3)

        # Synthetic return from the refund-driven restock (2 of 3 units). Shopify
        # restock = goods already back in stock, so the picking auto-validates on
        # creation and qty_delivered drops from 3 to 1 without a manual step.
        synthetic = self._create_return_record(
            order,
            external_id='refund-950343270614',
            lines=[{
                'external_str_id': 'refund-950343270614/ext-line-1',
                'external_line_str_id': 'ext-line-1',
                'quantity': 2,
            }],
        )
        synthetic.restocked_externally = True
        synthetic._process()
        self.assertEqual(len(synthetic.picking_ids), 1)
        synthetic.picking_ids.invalidate_recordset(['state'])
        self.assertEqual(
            synthetic.picking_ids.state, 'done',
            'Restock picking must be auto-validated on creation',
        )
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 1.0)

        # A real Return event later covers the remaining 1 unit.
        real = self._create_return_record(
            order,
            external_id='gid://shopify/Return/8000000000001',
            lines=[{
                'external_str_id': 'ret-line-real',
                'external_line_str_id': 'ext-line-1',
                'quantity': 1,
            }],
        )
        real._process()
        self.assertEqual(
            len(real.picking_ids), 1,
            'Guard must allow the real return for the remaining 1 unit '
            '(2 synthetic + 1 real = 3 delivered)',
        )

    def test_regular_return_picking_stays_in_ready(self):
        """A regular return (restocked_externally unset — goods still in transit
        from the customer) must NOT be auto-validated: its picking stays in Ready
        until the warehouse physically receives the goods. Counterpart to the
        restock flow; guards the 'don't auto-validate regular refunds' contract.
        """
        order, _picking = self._create_order_with_validated_delivery(qty=2)
        ret = self._create_return_record(order, lines=[{
            'external_str_id': 'ret-line-1',
            'external_line_str_id': 'ext-line-1',
            'quantity': 1,
        }])
        self.assertFalse(ret.restocked_externally)

        ret._process()

        self.assertEqual(len(ret.picking_ids), 1)
        ret.picking_ids.invalidate_recordset(['state'])
        self.assertIn(
            ret.picking_ids.state, ('assigned', 'confirmed', 'waiting'),
            'Regular return picking must wait in Ready, not be auto-validated',
        )
        # qty_delivered is unchanged until the warehouse validates the receipt.
        order.order_line.invalidate_recordset(['qty_delivered'])
        self.assertEqual(order.order_line.qty_delivered, 2.0)
