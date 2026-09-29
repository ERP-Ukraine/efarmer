# See LICENSE file for full copyright and licensing details.

import logging
from unittest.mock import patch as mock_patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase
from ..shopify.resources.order import Order
from ..shopify_api import ShopifyAPIClient


# Synthetic Shopify GIDs used across the tests.
TEST_ORDER_GID = 'gid://shopify/Order/9000000000001'
TEST_LINE_ITEM_GID = 'gid://shopify/LineItem/8000000000001'
TEST_FULFILLMENT_LINE_ITEM_GID = 'gid://shopify/FulfillmentLineItem/7000000000001'
# Shopify's returnCreate response carries a full Return GID; the connector stores
# the bare numeric id (id_str), matching the inbound returns/* parser — so the
# export row and the inbound webhook dedup against the same external_str_id.
TEST_RETURN_GID = 'gid://shopify/Return/6000000000001'
TEST_RETURN_ID = '6000000000001'
TEST_REVERSE_FULFILLMENT_ORDER_GID = 'gid://shopify/ReverseFulfillmentOrder/5000000000001'


def _stub_create_return(*_args, **_kwargs):
    """Mock create_return_for_order response — happy path."""
    return {
        'id': TEST_RETURN_GID,
        'status': 'OPEN',
        'reverse_fulfillment_order_id': TEST_REVERSE_FULFILLMENT_ORDER_GID,
        'reverse_fulfillment_order_line_items': [
            {
                'reverseFulfillmentOrderLineItemId':
                    'gid://shopify/ReverseFulfillmentOrderLineItem/7000000000001',
                'quantity': 1,
            },
        ],
    }


def _stub_create_return_no_rfo(*_args, **_kwargs):
    """Mock create_return_for_order response — Shopify did not return a
    reverseFulfillmentOrder (the E522 edge case)."""
    return {
        'id': TEST_RETURN_GID,
        'status': 'OPEN',
        'reverse_fulfillment_order_id': '',
    }


def _stub_fli_lookup_match(*_args, **_kwargs):
    """Mock fetch_fulfillment_line_item_lookup response — TEST_LINE_ITEM_GID
    resolves to a single fulfillment with plenty of returnable quantity."""
    return {TEST_LINE_ITEM_GID: [(TEST_FULFILLMENT_LINE_ITEM_GID, 10)]}


def _stub_fli_lookup_empty(*_args, **_kwargs):
    """Mock fetch_fulfillment_line_item_lookup response — no match."""
    return {}


def _stub_execute_returnable_fulfillments(*_args, **_kwargs):
    """Mock Order.execute() for the returnableFulfillments query — one returnable
    fulfillment line item. Shape matches a real response verified against a live
    store: quantity is what's still returnable, net of prior returns."""
    return {
        'data': {
            'returnableFulfillments': {
                'nodes': [
                    {
                        'returnableFulfillmentLineItems': {
                            'edges': [
                                {
                                    'node': {
                                        'quantity': 2,
                                        'fulfillmentLineItem': {
                                            'id': TEST_FULFILLMENT_LINE_ITEM_GID,
                                            'lineItem': {'id': TEST_LINE_ITEM_GID},
                                        },
                                    },
                                },
                            ],
                        },
                    },
                ],
            },
        },
    }


def _stub_execute_returnable_fulfillments_empty(*_args, **_kwargs):
    """Mock Order.execute() for the returnableFulfillments query — nothing
    returnable. Matches what a live store returns for a fulfillment that's
    either fully claimed by prior returns or not returnable at all (e.g.
    CANCELLED) — Shopify excludes it from the connection entirely rather than
    returning it with quantity 0."""
    return {'data': {'returnableFulfillments': {'nodes': []}}}


def _stub_attach_tracking_success(*_args, **_kwargs):
    return {'id': 'gid://shopify/ReverseDelivery/4000000000001'}


def _stub_attach_tracking_fail(*_args, **_kwargs):
    raise UserError('Shopify rejected the tracking attachment.')


@tagged('post_install', '-at_install', 'test_shopify_return_export')
class TestShopifyReturnExport(IntegrationShopifyBase):
    """Return export from Odoo to Shopify.

    Tests cover the orchestrator on `stock.picking.action_export_return_to_shopify`,
    pre-flight checks, the loop-prevention persistence path, and the best-effort
    tracking attachment.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The export button is gated on `enable_returns_refunds_sync`.
        cls.return_location = cls.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.integration.write({
            'enable_returns_refunds_sync': True,
            'default_return_location_id': cls.return_location.id,
        })

        cls.partner = cls.env['res.partner'].with_company(cls.company).create({
            'name': 'Phase 7 Test Customer',
        })

        # Order line external_id matches what the FLI lookup will resolve.
        cls.so_line_ext_id_numeric = TEST_LINE_ITEM_GID.rsplit('/', 1)[-1]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_shopify_order_with_delivered_picking(self, product=None, qty=1, integration=None):
        """Build a confirmed Shopify-bound SO with a validated outgoing picking.

        Also wires up a sale.integration.input.file so
        `sale_order.external_order_name` resolves — that's what the export
        adapter calls pass as the external order id.
        """
        product = product or self.product1
        integration = integration or self.integration
        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.partner.id,
            'integration_id': integration.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': product.list_price,
                'integration_external_id': self.so_line_ext_id_numeric,
            })],
        })
        external_order_id = TEST_ORDER_GID.rsplit('/', 1)[-1]
        self.env['sale.integration.input.file'].create({
            'si_id': integration.id,
            'name': external_order_id,
            'order_id': order.id,
            'raw_data': '{}',
        })
        order.action_confirm()
        outgoing = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing',
        )
        for move in outgoing.move_ids:
            move.quantity = move.product_uom_qty
        outgoing.with_context(skip_backorder=True, skip_sms=True).button_validate()
        self.assertEqual(outgoing.state, 'done')
        return order, outgoing

    def _create_return_picking(self, outgoing, qty=1):
        """Use the stock.return.picking wizard to make an incoming return picking."""
        wizard = self.env['stock.return.picking'].with_context(
            active_id=outgoing.id,
            active_model='stock.picking',
        ).create({})
        for ln in wizard.product_return_moves:
            ln.quantity = qty
        return wizard._create_return()

    def _patch_adapter(self, **overrides):
        """Patch one or more adapter methods on ShopifyAPIClient for this test."""
        for method_name, impl in overrides.items():
            patcher = mock_patch.object(ShopifyAPIClient, method_name, impl)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------
    # 1. Happy path
    # ------------------------------------------------------------------

    def test_return_export_happy_path(self):
        """Non-kit return picking, no tracking. Export creates an
        external.order.return with the Shopify GID and is_done=True.
        """
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return,
        )

        result = return_picking.action_export_return_to_shopify()

        self.assertEqual(result['type'], 'ir.actions.client')
        external_return = self.env['external.order.return'].search([
            ('external_str_id', '=', TEST_RETURN_ID),
        ])
        self.assertEqual(len(external_return), 1)
        self.assertEqual(external_return.internal_status, 'done')
        self.assertTrue(external_return.is_done)
        self.assertEqual(external_return.state, 'open')
        self.assertIn(return_picking, external_return.picking_ids)

        messages = return_picking.message_ids.mapped('body')
        self.assertTrue(
            any(TEST_RETURN_ID in m for m in messages),
            'Expected the Shopify Return id in the chatter.',
        )

    # ------------------------------------------------------------------
    # 2. With tracking — both mutations called and succeed.
    # ------------------------------------------------------------------

    def test_return_export_with_tracking(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)
        return_picking.carrier_tracking_ref = '1Z999AA10123456789'

        called = {'tracking': 0, 'line_items': None}

        def _spy_attach(*args, **kwargs):
            called['tracking'] += 1
            called['line_items'] = kwargs.get('reverse_delivery_line_items')
            return {'id': 'gid://shopify/ReverseDelivery/x'}

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return,
            attach_tracking_to_return=_spy_attach,
        )

        return_picking.action_export_return_to_shopify()

        self.assertEqual(called['tracking'], 1)
        # reverseDeliveryCreateWithShipping requires a non-empty reverseDeliveryLineItems;
        # the orchestrator must forward what create_return() returned.
        self.assertTrue(
            called['line_items'],
            'Tracking attachment must forward reverse_delivery_line_items.',
        )
        messages = return_picking.message_ids.mapped('body')
        self.assertTrue(
            any('1Z999AA10123456789' in m for m in messages),
            'Chatter should mention the tracking number on success.',
        )

    # ------------------------------------------------------------------
    # 3. Tracking call fails — return creation still committed.
    # ------------------------------------------------------------------

    def test_return_export_tracking_fails_return_succeeds(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)
        return_picking.carrier_tracking_ref = '1Z999AA10123456789'

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return,
            attach_tracking_to_return=_stub_attach_tracking_fail,
        )

        # The tracking failure is intentional (that's what this test exercises), so
        # assertLogs both captures and mutes the WARNING it would otherwise print, while still
        # failing the test if the code stops logging it at all.
        with self.assertLogs('odoo.addons.integration_shopify.models.stock_picking', logging.WARNING):
            return_picking.action_export_return_to_shopify()

        # Return creation must persist despite the tracking failure.
        external_return = self.env['external.order.return'].search([
            ('external_str_id', '=', TEST_RETURN_ID),
        ])
        self.assertEqual(len(external_return), 1)
        self.assertTrue(external_return.is_done)

        # Chatter must surface the failure to the merchant.
        messages = return_picking.message_ids.mapped('body')
        self.assertTrue(
            any('Tracking attachment failed' in m for m in messages),
            'Chatter should mention that tracking attachment failed.',
        )

    # ------------------------------------------------------------------
    # 4. Idempotency — E520 on second click.
    # ------------------------------------------------------------------

    def test_return_export_idempotency(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return,
        )

        return_picking.action_export_return_to_shopify()

        with self.assertRaises(UserError) as cm:
            return_picking.action_export_return_to_shopify()
        self.assertIn('E520', cm.exception.args[0])

    # ------------------------------------------------------------------
    # 5. Loop prevention — inbound webhook for the same return is a no-op.
    # ------------------------------------------------------------------

    def test_return_export_loop_prevention(self):
        """After export, the inbound returns/* webhook arrives for the same
        return id. _get_or_create_from_external must find the existing record,
        _validate() must short-circuit on is_done, no duplicate picking.
        """
        order, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return,
        )

        return_picking.action_export_return_to_shopify()
        external_return_before = self.env['external.order.return'].search([
            ('external_str_id', '=', TEST_RETURN_ID),
        ])
        pickings_before = self.env['stock.picking'].search([
            ('sale_id', '=', order.id),
            ('picking_type_id.code', '=', 'incoming'),
        ])
        self.assertEqual(len(external_return_before), 1)

        # Simulate the inbound parse → _get_or_create_from_external flow. The parser
        # stores the bare numeric id, which must match the numeric id the export wrote.
        inbound_dict = {
            'external_str_id': TEST_RETURN_ID,
            'state': 'open',
            'lines': [{
                'external_str_id': 'inbound-line-1',
                'external_line_str_id': TEST_LINE_ITEM_GID,
                'quantity': 1,
            }],
        }
        Return = self.env['external.order.return'].with_context(
            integration_id=self.integration.id,
            erp_order_id=order.id,
        )
        record = Return._get_or_create_from_external(inbound_dict)
        success, __ = record.validate()

        # Same record, no new picking, no error.
        self.assertEqual(record, external_return_before)
        self.assertTrue(success)
        pickings_after = self.env['stock.picking'].search([
            ('sale_id', '=', order.id),
            ('picking_type_id.code', '=', 'incoming'),
        ])
        self.assertEqual(pickings_after, pickings_before)

    # ------------------------------------------------------------------
    # 6. Non-Shopify integration — E521.
    # ------------------------------------------------------------------

    def test_return_export_non_shopify_integration(self):
        no_api_integration = self.env['sale.integration'].create({
            'name': 'Test No-API Integration',
            'type_api': 'no_api',
            'company_id': self.company.id,
            'enable_returns_refunds_sync': True,
        })
        __, outgoing = self._create_shopify_order_with_delivered_picking(
            integration=no_api_integration,
        )
        return_picking = self._create_return_picking(outgoing)

        # Form-view visibility: the button must be hidden.
        return_picking.invalidate_recordset(['is_shopify_return_export_eligible'])
        self.assertFalse(return_picking.is_shopify_return_export_eligible)

        # Programmatic call must fail-loud with E521.
        with self.assertRaises(UserError) as cm:
            return_picking.action_export_return_to_shopify()
        self.assertIn('E521', cm.exception.args[0])

    # ------------------------------------------------------------------
    # 7. Tracking set but Shopify did not return a reverseFulfillmentOrder.
    # ------------------------------------------------------------------

    def test_return_export_missing_rfo_with_tracking_raises_e522(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)
        return_picking.carrier_tracking_ref = '1Z999AA10123456789'

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_match,
            create_return_for_order=_stub_create_return_no_rfo,
        )

        with self.assertRaises(UserError) as cm:
            return_picking.action_export_return_to_shopify()
        self.assertIn('E522', cm.exception.args[0])

    # ------------------------------------------------------------------
    # 8. A sale.order.line's quantity is split across multiple Shopify
    #    fulfillments instead of being dumped onto a single FLI GID.
    # ------------------------------------------------------------------

    def test_return_export_quantity_split_across_multiple_fulfillments(self):
        """The order LineItem behind this SO line was shipped in two separate
        Shopify fulfillments (staged/partial shipment). The return quantity must
        be split across both FulfillmentLineItem GIDs, each capped at its own
        returnable quantity, instead of being sent whole against a single one
        (which is what used to make Shopify reject it as an invalid quantity).
        """
        __, outgoing = self._create_shopify_order_with_delivered_picking(qty=12)
        return_picking = self._create_return_picking(outgoing, qty=12)

        fli_gid_a = TEST_FULFILLMENT_LINE_ITEM_GID
        fli_gid_b = 'gid://shopify/FulfillmentLineItem/7000000000002'
        captured = {}

        def _stub_fli_lookup_split(*_args, **_kwargs):
            return {TEST_LINE_ITEM_GID: [(fli_gid_a, 6), (fli_gid_b, 16)]}

        def _spy_create_return(*args, **kwargs):
            captured['return_line_items'] = args[2] if len(args) > 2 else kwargs.get('return_line_items')
            return _stub_create_return()

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_split,
            create_return_for_order=_spy_create_return,
        )

        return_picking.action_export_return_to_shopify()

        return_line_items = captured['return_line_items']
        self.assertEqual(len(return_line_items), 2)
        qty_by_gid = {l['fulfillmentLineItemId']: l['quantity'] for l in return_line_items}
        # fli_gid_a can only cover 6 of the 12 requested; the rest must come from fli_gid_b.
        self.assertEqual(qty_by_gid[fli_gid_a], 6)
        self.assertEqual(qty_by_gid[fli_gid_b], 6)

    # ------------------------------------------------------------------
    # 9. Requested quantity exceeds what Shopify still considers returnable
    #    across every fulfillment for that line — E521, not a partial export.
    # ------------------------------------------------------------------

    def test_return_export_quantity_exceeds_returnable_raises_e521(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking(qty=12)
        return_picking = self._create_return_picking(outgoing, qty=12)

        def _stub_fli_lookup_insufficient(*_args, **_kwargs):
            return {TEST_LINE_ITEM_GID: [(TEST_FULFILLMENT_LINE_ITEM_GID, 6)]}

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_insufficient,
            create_return_for_order=_stub_create_return,
        )

        with self.assertRaises(UserError) as cm:
            return_picking.action_export_return_to_shopify()
        self.assertIn('E521', cm.exception.args[0])

    # ------------------------------------------------------------------
    # 10. No FulfillmentLineItem at all for this line — E521 (not an
    #     AttributeError from the unresolved-lines message building).
    # ------------------------------------------------------------------

    def test_return_export_unresolved_fulfillment_line_item_raises_e521(self):
        __, outgoing = self._create_shopify_order_with_delivered_picking()
        return_picking = self._create_return_picking(outgoing)

        self._patch_adapter(
            fetch_fulfillment_line_item_lookup=_stub_fli_lookup_empty,
            create_return_for_order=_stub_create_return,
        )

        with self.assertRaises(UserError) as cm:
            return_picking.action_export_return_to_shopify()
        self.assertIn('E521', cm.exception.args[0])

    # ------------------------------------------------------------------
    # 11. fetch_fulfillment_line_item_lookup() itself — parses the
    #     returnableFulfillments response into the {LineItem GID: [(FLI GID,
    #     qty), ...]} lookup the tests above stub out. Mocks Order.execute()
    #     (the network boundary) rather than the lookup method, so these are
    #     the only tests in this file that exercise the real GraphQL parsing.
    # ------------------------------------------------------------------

    def test_fetch_fulfillment_line_item_lookup_returns_returnable_quantity(self):
        """The parsed quantity is what returnableFulfillments reports as still
        returnable, not a raw fulfilled total — confirmed against a live store
        (see the comment on QUERY_FULFILLMENT_LINE_ITEMS_FOR_EXPORT)."""
        external_order_id = TEST_ORDER_GID.rsplit('/', 1)[-1]

        with mock_patch.object(Order, 'execute', _stub_execute_returnable_fulfillments):
            lookup = self.integration.adapter.fetch_fulfillment_line_item_lookup(external_order_id)

        self.assertEqual(lookup, {TEST_LINE_ITEM_GID: [(TEST_FULFILLMENT_LINE_ITEM_GID, 2)]})

    def test_fetch_fulfillment_line_item_lookup_empty_when_nothing_returnable(self):
        """No node in the response means no entry in the lookup — the caller's
        E521 unresolved-line path handles this the same as any other miss.
        Also covers the CANCELLED-fulfillment case: returnableFulfillments
        excludes those by itself, so there is no client-side status filter to
        get wrong (confirmed against a live store)."""
        external_order_id = TEST_ORDER_GID.rsplit('/', 1)[-1]

        with mock_patch.object(Order, 'execute', _stub_execute_returnable_fulfillments_empty):
            lookup = self.integration.adapter.fetch_fulfillment_line_item_lookup(external_order_id)

        self.assertEqual(lookup, {})
