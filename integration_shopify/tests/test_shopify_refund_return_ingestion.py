# See LICENSE file for full copyright and licensing details.

import json
import os

from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase


FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'refund_payloads',
)


def _load_fixture(filename):
    with open(os.path.join(FIXTURE_DIR, filename)) as f:
        return json.load(f)


@tagged('post_install', '-at_install', 'test_shopify_refund_return_ingestion')
class TestShopifyRefundReturnIngestion(IntegrationShopifyBase):
    """Acceptance tests for Shopify Returns & Refunds ingestion.

    Tests validate the full chain: fixture JSON -> parse_refunds/parse_returns
    -> _prepare_vals_from_external -> _get_or_create_from_external ->
    external.order.refund / external.order.return records in Odoo.

    Also covers parser-level guards: store-credit/gift-card detection, plus
    the original-quantity / total-price behaviour when refund sync is enabled.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up a bank journal for refund payments (required by constraint)
        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.bank_journal:
            cls.bank_journal = cls.env['account.journal'].create({
                'name': 'Test Bank',
                'type': 'bank',
                'code': 'T4AK',
                'company_id': cls.company.id,
            })

        # Enable returns/refunds sync on the test integration
        cls.integration.write({
            'enable_returns_refunds_sync': True,
        })

        # Create EUR currency (active) for refund amounts
        cls.eur = cls.env['res.currency'].search(
            [('name', '=', 'EUR')], limit=1,
        )
        if not cls.eur:
            cls.eur = cls.env['res.currency'].create({
                'name': 'EUR',
                'symbol': '\u20ac',
                'rounding': 0.01,
            })
        if not cls.eur.active:
            cls.eur.active = True

    def _parse_fixture(self, filename):
        """Load a fixture and parse refunds/returns using the Order resource."""
        fixture = _load_fixture(filename)
        order_data = fixture['data']['order']

        # Use the adapter's GQL Order resource to parse
        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(
            use_customer_currency=False,
        )
        return {
            'order_refunds': order.parse_refunds(),
            'order_returns': order.parse_returns(),
            'order_data': order_data,
        }

    def _create_order_with_line(self, external_order_id, line_ids_data):
        """Create a sale order with integration and specified line IDs."""
        order_lines = []
        for line_data in line_ids_data:
            order_lines.append((0, 0, {
                'product_id': self.product1.id,
                'product_uom_qty': line_data.get('qty', 1),
                'price_unit': line_data.get('price', 19.84),
                'integration_external_id': line_data['external_id'],
            }))

        order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.env['res.partner'].with_company(
                self.company,
            ).create({
                'name': 'Test Refund Customer',
            }).id,
            'integration_id': self.integration.id,
            'order_line': order_lines,
        })
        return order

    def _ingest_refunds_and_returns(self, order, parsed):
        """Feed parsed refunds/returns into the base ingestion chain.

        Order matches production (sale_order._apply_values_from_external):
        returns first, then refunds — so external.order.refund.linked_return_id
        can be resolved from linked_return_str_id at refund-create time.
        """
        vals = {}
        if parsed.get('order_returns'):
            Return = self.env['external.order.return'].with_context(
                integration_id=self.integration.id,
                erp_order_id=order.id,
            )
            returns = []
            for return_data in parsed['order_returns']:
                record = Return._get_or_create_from_external(return_data)
                returns.append((4, record.id, 0))
            vals['external_return_ids'] = returns

        if parsed.get('order_refunds'):
            Refund = self.env['external.order.refund'].with_context(
                integration_id=self.integration.id,
                erp_order_id=order.id,
            )
            refunds = []
            for refund_data in parsed['order_refunds']:
                record = Refund._get_or_create_from_external(refund_data)
                refunds.append((4, record.id, 0))
            vals['external_refund_ids'] = refunds

        if vals:
            order.write(vals)

    # -------------------------------------------------------------------------
    # UC-1: Refund without return
    # -------------------------------------------------------------------------

    def test_uc1_refund_without_return(self):
        """UC-1: Full refund with NO_RESTOCK, no linked return. Validates
        refund record fields, line-level amounts, tax, and is_ecommerce_ok."""
        parsed = self._parse_fixture('order1-refund-without-return.json')

        order = self._create_order_with_line(
            'gid://shopify/Order/6635869995222',
            [{'external_id': '15681092944086',
              'qty': 1, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(
            len(order.external_refund_ids), 1,
            'Expected exactly 1 refund record',
        )
        self.assertEqual(len(order.external_return_ids), 0)

        refund = order.external_refund_ids[0]
        self.assertEqual(
            refund.external_str_id, '946849251542',
        )
        self.assertAlmostEqual(refund.total_refunded_amount, 19.84, places=2)
        self.assertEqual(refund.currency_id, self.eur)
        self.assertEqual(refund.note, 'Testing Refunds & Returns')
        self.assertFalse(refund.linked_return_str_id)

        # Refund line assertions
        self.assertEqual(len(refund.line_ids), 1)
        line = refund.line_ids[0]
        self.assertEqual(
            line.external_line_str_id,
            '15681092944086',
        )
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.restock_type, 'no_restock')
        self.assertAlmostEqual(line.original_unit_price, 19.84, places=2)
        self.assertAlmostEqual(line.subtotal, 19.84, places=2)
        self.assertAlmostEqual(line.total_tax, 3.71, places=2)

        self.assertTrue(refund.is_ecommerce_ok)

    # -------------------------------------------------------------------------
    # Shipping-fee refund (refundShippingLines)
    # -------------------------------------------------------------------------

    def test_refund_with_shipping_emits_shipping_line(self):
        """A Shopify refund carrying refundShippingLines emits a dedicated
        is_shipping refund line (subtotal = Σ subtotalAmountSet, tax =
        Σ taxAmountSet, no product/external id). The base credit note flow
        then matches it to the delivery line so the shipping refund is not
        dropped."""
        fixture = _load_fixture('order1-refund-without-return.json')
        order_data = fixture['data']['order']
        # Inject a refunded shipping line in the raw GraphQL edges/nodes shape;
        # Order.set flattens it like the other connections.
        order_data['refunds'][0]['refundShippingLines'] = {'edges': [{'node': {
            'id': 'gid://shopify/RefundShippingLine/1',
            'subtotalAmountSet': {'shopMoney': {'amount': '5.95', 'currencyCode': 'EUR'}},
            'taxAmountSet': {'shopMoney': {'amount': '1.05', 'currencyCode': 'EUR'}},
        }}]}

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(use_customer_currency=False)
        refunds = order.parse_refunds()

        self.assertEqual(len(refunds), 1)
        lines = refunds[0]['lines']
        shipping = [ln for ln in lines if ln.get('is_shipping')]
        self.assertEqual(len(shipping), 1, 'A shipping refund line must be emitted')
        self.assertAlmostEqual(shipping[0]['subtotal'], 5.95, places=2)
        self.assertAlmostEqual(shipping[0]['total_tax'], 1.05, places=2)
        self.assertEqual(shipping[0]['external_line_str_id'], '')
        self.assertEqual(shipping[0]['currency_code'], 'EUR')
        # Original product refund line is still present alongside the shipping line.
        self.assertEqual(len(lines), 2)
        self.assertEqual(len([ln for ln in lines if not ln.get('is_shipping')]), 1)

    def test_refund_without_shipping_emits_no_shipping_line(self):
        """Control: a refund with no refundShippingLines emits no is_shipping
        line (the product-only path is unchanged)."""
        parsed = self._parse_fixture('order1-refund-without-return.json')
        refund = parsed['order_refunds'][0]
        self.assertFalse([ln for ln in refund['lines'] if ln.get('is_shipping')])

    # -------------------------------------------------------------------------
    # UC-2a: Return in progress, no refund yet
    # -------------------------------------------------------------------------

    def test_uc2a_return_in_progress_no_refund(self):
        """UC-2a: Return with status=OPEN, no refund. Validates return record
        fields, tracking info, return reason, and is_ecommerce_ok."""
        parsed = self._parse_fixture(
            'order1-return-without-refund-return-in-progress.json',
        )

        order = self._create_order_with_line(
            'gid://shopify/Order/6635875467478',
            [{'external_id': '15681101070550',
              'qty': 1, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(len(order.external_refund_ids), 0)
        self.assertEqual(len(order.external_return_ids), 1)

        ret = order.external_return_ids[0]
        self.assertEqual(
            ret.external_str_id, '19719323862',
        )
        self.assertEqual(ret.state, 'open')
        self.assertEqual(ret.return_reason_summary, 'Customer changed their mind')
        self.assertEqual(ret.reverse_tracking_number, 'bp39399393pl')
        self.assertEqual(ret.reverse_tracking_carrier, 'Bpost')

        self.assertEqual(len(ret.line_ids), 1)
        line = ret.line_ids[0]
        self.assertEqual(
            line.external_line_str_id,
            '15681101070550',
        )
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.return_reason, 'Customer changed their mind')

        self.assertTrue(ret.is_ecommerce_ok)

    # -------------------------------------------------------------------------
    # UC-2b: Return finished (CLOSED), placeholder refund
    # -------------------------------------------------------------------------

    def test_uc2b_closed_return_with_placeholder_refund(self):
        """UC-2b: Return closed + zero-amount refund (placeholder). Validates
        return state=closed, refund amount=0 with linked_return_str_id, AND
        that linked_return_id resolves to the paired return record so the
        placeholder branch in _process() is reachable."""
        parsed = self._parse_fixture(
            'order1-return-without-refund-finished-return-no-refund.json',
        )

        order = self._create_order_with_line(
            'gid://shopify/Order/6635875467478',
            [{'external_id': '15681101070550',
              'qty': 1, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(len(order.external_refund_ids), 1)
        self.assertEqual(len(order.external_return_ids), 1)

        refund = order.external_refund_ids[0]
        self.assertAlmostEqual(refund.total_refunded_amount, 0.0, places=2)
        self.assertEqual(
            refund.linked_return_str_id,
            '19719323862',
        )

        ret = order.external_return_ids[0]
        self.assertEqual(ret.state, 'closed')

        # linked_return_id must resolve to the paired return record at
        # ingestion time (returns are ingested before refunds so the lookup
        # in _prepare_vals_from_external succeeds). Without this, the
        # placeholder branch in external.order.refund._process is unreachable
        # and the refund sits in draft forever.
        self.assertEqual(
            refund.linked_return_id, ret,
            'linked_return_id must resolve to the paired return at ingestion',
        )
        self.assertTrue(
            refund.is_placeholder,
            'Zero-amount refund with a linked return is a placeholder',
        )

    # -------------------------------------------------------------------------
    # UC-3: Partial return with partial refund
    # -------------------------------------------------------------------------

    def test_uc3_partial_return_with_partial_refund(self):
        """UC-3: 1 of 3 items returned + refunded. Validates linkage,
        tracking, restock_type=return, and external_location_str_id."""
        parsed = self._parse_fixture(
            'order2-partial-return-with-partial-refund.json',
        )

        order = self._create_order_with_line(
            'gid://shopify/Order/6635887919318',
            [{'external_id': '15681118339286',
              'qty': 3, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(len(order.external_refund_ids), 1)
        self.assertEqual(len(order.external_return_ids), 1)

        refund = order.external_refund_ids[0]
        self.assertAlmostEqual(refund.total_refunded_amount, 19.84, places=2)
        self.assertEqual(
            refund.linked_return_str_id,
            '19719454934',
        )

        ret = order.external_return_ids[0]
        self.assertEqual(ret.state, 'closed')
        self.assertEqual(ret.reverse_tracking_number, 'dhl11122233444pl')
        self.assertEqual(ret.reverse_tracking_carrier, 'DHL Express')

        self.assertEqual(len(ret.line_ids), 1)
        self.assertEqual(ret.line_ids[0].quantity, 1)
        self.assertEqual(ret.line_ids[0].return_reason, 'Received the wrong item')

        self.assertEqual(len(refund.line_ids), 1)
        self.assertEqual(refund.line_ids[0].restock_type, 'return')
        self.assertEqual(
            refund.line_ids[0].external_location_str_id,
            '72493924566',
        )

    # -------------------------------------------------------------------------
    # UC-4: Full return with full refund
    # -------------------------------------------------------------------------

    def test_uc4_full_return_with_full_refund(self):
        """UC-4: All items returned + fully refunded. Validates total amount,
        return state, and line quantities/reasons."""
        parsed = self._parse_fixture(
            'order3-full-return-with-full-refund.json',
        )

        order = self._create_order_with_line(
            'gid://shopify/Order/6635893620950',
            [{'external_id': '15681127416022',
              'qty': 2, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(len(order.external_refund_ids), 1)
        self.assertEqual(len(order.external_return_ids), 1)

        refund = order.external_refund_ids[0]
        self.assertAlmostEqual(refund.total_refunded_amount, 39.68, places=2)

        ret = order.external_return_ids[0]
        self.assertEqual(ret.state, 'closed')
        self.assertEqual(ret.line_ids[0].quantity, 2)
        self.assertEqual(ret.line_ids[0].return_reason, 'Size was too small')

    # -------------------------------------------------------------------------
    # UC-5: Partial return + refund with discount
    # -------------------------------------------------------------------------

    def test_uc5_partial_refund_with_discount(self):
        """UC-5: Refund where priceSet != subtotalSet (discount applied).
        Validates discount_for_refund = original_unit_price * qty - subtotal."""
        parsed = self._parse_fixture(
            'order-4-partial-return-partial-refund-with-discount.json',
        )

        order = self._create_order_with_line(
            'gid://shopify/Order/6635919474902',
            [{'external_id': '15681167032534',
              'qty': 2, 'price': 19.84}],
        )
        self._ingest_refunds_and_returns(order, parsed)

        self.assertEqual(len(order.external_refund_ids), 1)
        self.assertEqual(len(order.external_return_ids), 1)

        refund = order.external_refund_ids[0]
        self.assertAlmostEqual(refund.total_refunded_amount, 12.34, places=2)

        self.assertEqual(len(refund.line_ids), 1)
        line = refund.line_ids[0]
        self.assertAlmostEqual(line.original_unit_price, 19.84, places=2)
        self.assertAlmostEqual(line.subtotal, 12.34, places=2)
        self.assertAlmostEqual(line.discount_for_refund, 7.50, places=2)

        ret = order.external_return_ids[0]
        self.assertEqual(ret.line_ids[0].return_reason, 'Color')

    # -------------------------------------------------------------------------
    # Idempotency
    # -------------------------------------------------------------------------

    def test_double_ingestion_is_idempotent(self):
        """Ingesting the same fixture twice does not create duplicate records.
        Validates _get_or_create_from_external dedup behavior."""
        parsed = self._parse_fixture('order1-refund-without-return.json')

        order = self._create_order_with_line(
            'gid://shopify/Order/6635869995222',
            [{'external_id': '15681092944086',
              'qty': 1, 'price': 19.84}],
        )

        self._ingest_refunds_and_returns(order, parsed)
        self.assertEqual(len(order.external_refund_ids), 1)

        self._ingest_refunds_and_returns(order, parsed)
        self.assertEqual(
            len(order.external_refund_ids), 1,
            'Duplicate refund created on re-ingestion',
        )

    # -------------------------------------------------------------------------
    # Refunded lines gated by enable_returns_refunds_sync
    # -------------------------------------------------------------------------

    def test_refunded_lines_excluded_when_sync_disabled(self):
        """When refund sync is OFF, lines with currentQuantity=0 are excluded
        from parse_lines() (backward-compatible behavior)."""
        fixture = _load_fixture('order3-full-return-with-full-refund.json')
        order_data = fixture['data']['order']

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(
            use_customer_currency=False,
            enable_returns_refunds_sync=False,
        )

        lines = order.parse_lines()
        self.assertEqual(
            len(lines), 0,
            'Lines with currentQuantity=0 should be excluded when sync disabled',
        )

    def test_refunded_lines_use_original_qty_when_sync_enabled(self):
        """When refund sync is ON, lines with currentQuantity=0 are included
        and use the *original* quantity (refund processing needs the full
        original order to build correct credit notes)."""
        fixture = _load_fixture('order3-full-return-with-full-refund.json')
        order_data = fixture['data']['order']

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(
            use_customer_currency=False,
            enable_returns_refunds_sync=True,
        )

        lines = order.parse_lines()
        self.assertGreater(
            len(lines), 0,
            'Lines with currentQuantity=0 should be included when sync enabled',
        )
        # Original quantity was 2 (fixture: quantity=2, currentQuantity=0)
        self.assertEqual(
            lines[0]['product_uom_qty'], 2,
            'Should use original quantity, not currentQuantity',
        )

    def test_partial_return_uses_original_qty_when_sync_enabled(self):
        """When refund sync is ON, lines with currentQuantity < quantity
        (partially returned) use the original quantity, not Shopify's
        decremented currentQuantity."""
        fixture = _load_fixture(
            'order2-partial-return-with-partial-refund.json',
        )
        order_data = fixture['data']['order']

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(
            use_customer_currency=False,
            enable_returns_refunds_sync=True,
        )

        lines = order.parse_lines()
        self.assertGreater(len(lines), 0)
        # Fixture: quantity=3, currentQuantity=2 (1 item returned)
        self.assertEqual(
            lines[0]['product_uom_qty'], 3,
            'Should use original quantity (3), not currentQuantity (2)',
        )

    # -------------------------------------------------------------------------
    # totalPriceSet vs currentTotalPriceSet
    # -------------------------------------------------------------------------

    def test_price_total_uses_original_when_sync_enabled(self):
        """parse_price_total() returns totalPriceSet (pre-refund) when refund
        sync is ON — must match the original-quantity lines emitted above so
        the framework's total-vs-lines check accepts the order."""
        fixture = _load_fixture('order3-full-return-with-full-refund.json')
        order_data = fixture['data']['order']

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(
            use_customer_currency=False,
            enable_returns_refunds_sync=True,
        )
        total_sync_on = order.parse_price_total()

        order2 = self.adapter.gql.Order.set(**order_data)
        order2.update_props(
            use_customer_currency=False,
            enable_returns_refunds_sync=False,
        )
        total_sync_off = order2.parse_price_total()

        # Fixture: totalPriceSet=53.68, currentTotalPriceSet=14.0
        self.assertAlmostEqual(
            total_sync_on, 53.68, places=2,
            msg='Sync enabled should use totalPriceSet (pre-refund)',
        )
        self.assertAlmostEqual(
            total_sync_off, 14.0, places=2,
            msg='Sync disabled should use currentTotalPriceSet (post-refund)',
        )

    # -------------------------------------------------------------------------
    # Multi-currency: refund parser honours use_customer_currency in both modes
    # -------------------------------------------------------------------------

    def _parse_synthetic_multi_currency(self, use_customer_currency):
        """Load the synthetic multi-currency fixture and run the refund
        parser at the requested currency mode. Returns the parsed refund
        dict (one refund in the fixture).
        """
        fixture = _load_fixture('refund_multi_currency_synthetic.json')
        order_data = fixture['data']['order']
        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(use_customer_currency=use_customer_currency)
        refunds = order.parse_refunds()
        self.assertEqual(len(refunds), 1)
        return refunds[0]

    def test_refund_uses_shop_currency_when_use_customer_currency_false(self):
        """Default mode (use_customer_currency=False): refund amounts read
        from shopMoney. Fixture has shopMoney=100 EUR, presentmentMoney=108 USD.
        """
        refund = self._parse_synthetic_multi_currency(use_customer_currency=False)

        self.assertAlmostEqual(refund['total_refunded_amount'], 100.0, places=2)
        self.assertEqual(refund['currency_code'], 'EUR')
        self.assertEqual(len(refund['lines']), 1)
        line = refund['lines'][0]
        self.assertAlmostEqual(line['subtotal'], 100.0, places=2)
        self.assertAlmostEqual(line['original_unit_price'], 100.0, places=2)
        self.assertEqual(line['currency_code'], 'EUR')

    def test_refund_uses_presentment_currency_when_use_customer_currency_true(self):
        """Customer-currency mode: refund amounts read from presentmentMoney.
        Before the GraphQL template carried presentmentMoney for refunds, this
        path returned 0 amounts and EUR currency — the zero-amount-refund guard
        would fire (zero refund without linked return). Now amounts come back as
        108 USD as fetched.
        """
        refund = self._parse_synthetic_multi_currency(use_customer_currency=True)

        self.assertAlmostEqual(refund['total_refunded_amount'], 108.0, places=2)
        self.assertEqual(refund['currency_code'], 'USD')
        self.assertEqual(len(refund['lines']), 1)
        line = refund['lines'][0]
        self.assertAlmostEqual(line['subtotal'], 108.0, places=2)
        self.assertAlmostEqual(line['original_unit_price'], 108.0, places=2)
        self.assertEqual(line['currency_code'], 'USD')

    # -------------------------------------------------------------------------
    # Legacy refund-driven restock: synthesize a return alongside the refund
    # (Shopify's order-level "Refund" action with restock, no Return entity)
    # -------------------------------------------------------------------------

    # The real refund / LineItem ids from order #1674 — the exact payload that
    # triggered this fix. Stored numeric (id_str), as the parser emits.
    _R1674_LINE_ID = '15868937732310'
    _R1674_SYNTHETIC_RETURN_ID = 'refund-950343270614'

    def test_shopify_refund_with_restock_synthesizes_return(self):
        """Order #1674: refund line restockType=RETURN, refund.return null,
        returns.edges empty. The parser must synthesize a return record
        (external_str_id='refund-<refund_id>') with the restocked line, and
        the refund must link to it via linked_return_str_id."""
        parsed = self._parse_fixture('order1674-refund-restock-no-return.json')

        # Exactly one synthetic return, marked by the 'refund-' prefix.
        returns = parsed['order_returns']
        self.assertEqual(len(returns), 1, 'Expected one synthesized return')
        synth = returns[0]
        self.assertEqual(synth['external_str_id'], self._R1674_SYNTHETIC_RETURN_ID)
        # Synthetic restock returns are terminal ('closed'): no real Shopify Return
        # entity exists to change state later, and the goods are already restocked.
        self.assertEqual(synth['state'], 'closed')
        # Restock means the goods are already back in stock → validate immediately.
        self.assertTrue(
            synth.get('restocked_externally'),
            'Synthetic restock return must carry restocked_externally=True',
        )

        # One return line mirroring the restocked refund line (2 of 3 beanies).
        self.assertEqual(len(synth['lines']), 1)
        ret_line = synth['lines'][0]
        self.assertEqual(ret_line['external_line_str_id'], self._R1674_LINE_ID)
        self.assertEqual(ret_line['quantity'], 2)
        self.assertEqual(ret_line['external_sku'], 'woo-beanie')
        # Empty fulfillment id → base flow uses the single-picking fallback.
        self.assertEqual(ret_line['external_fulfillment_str_id'], '')

        # The refund parses normally and links to the synthetic return.
        refunds = parsed['order_refunds']
        self.assertEqual(len(refunds), 1)
        refund = refunds[0]
        self.assertEqual(
            refund['linked_return_str_id'], self._R1674_SYNTHETIC_RETURN_ID,
            'Refund must link to the synthesized return',
        )
        self.assertAlmostEqual(refund['total_refunded_amount'], 40.0, places=2)
        # Refund keeps its real restockType (the synthetic return owns the
        # picking; the refund still produces the credit note + payment).
        self.assertEqual(refund['lines'][0]['restock_type'], 'return')
        self.assertEqual(refund['lines'][0]['quantity'], 2)

    def test_shopify_refund_no_restock_no_synthetic_return(self):
        """Same payload but restockType=NO_RESTOCK: no return is synthesized
        (the customer keeps the goods), and the refund parses with no linked
        return."""
        fixture = _load_fixture('order1674-refund-restock-no-return.json')
        order_data = fixture['data']['order']
        order_data['refunds'][0]['refundLineItems']['edges'][0]['node'][
            'restockType'
        ] = 'NO_RESTOCK'

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(use_customer_currency=False)

        self.assertEqual(
            order.parse_returns(), [],
            'NO_RESTOCK must not synthesize a return',
        )
        refunds = order.parse_refunds()
        self.assertEqual(len(refunds), 1)
        self.assertEqual(
            refunds[0]['linked_return_str_id'], '',
            'NO_RESTOCK refund must have no linked return',
        )
        self.assertEqual(refunds[0]['lines'][0]['restock_type'], 'no_restock')

    def test_shopify_refund_with_linked_return_no_synthetic(self):
        """When Shopify already modelled a real Return (refund.return populated,
        the newer Returns API path), the real return takes precedence — no
        synthetic return is emitted, and the refund links to the real one."""
        # Inject a real Return as Shopify would (full GID); the parser stores the
        # bare numeric id, which is what the assertions below compare against.
        real_return_gid = 'gid://shopify/Return/6000000000777'
        real_return_id = '6000000000777'
        fixture = _load_fixture('order1674-refund-restock-no-return.json')
        order_data = fixture['data']['order']
        order_data['refunds'][0]['return'] = {'id': real_return_gid}
        # A real Return entity exists on the order alongside it.
        order_data['returns'] = {'edges': [{'node': {
            'id': real_return_gid,
            'status': 'OPEN',
            'returnLineItems': {'edges': []},
        }}]}

        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(use_customer_currency=False)

        returns = order.parse_returns()
        # No synthetic 'refund-' prefixed return; the single real return stands.
        self.assertFalse(
            any(r['external_str_id'].startswith('refund-') for r in returns),
            'No synthetic return when a real Return entity exists',
        )
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0]['external_str_id'], real_return_id)
        # A real return waits for physical receipt — it is NOT auto-validated.
        self.assertFalse(
            returns[0].get('restocked_externally'),
            'Real returns must not carry restocked_externally',
        )

        refunds = order.parse_refunds()
        self.assertEqual(
            refunds[0]['linked_return_str_id'], real_return_id,
            'Refund must link to the real return, not a synthetic one',
        )

    def test_synthetic_return_idempotent_on_reimport(self):
        """Ingesting the synthesized return twice creates only one record
        (dedup on the stable 'refund-<gid>' external_str_id), and the refund
        resolves its linked_return_id to that record."""
        parsed = self._parse_fixture('order1674-refund-restock-no-return.json')
        order = self._create_order_with_line(
            'gid://shopify/Order/6762388586710',
            [{'external_id': self._R1674_LINE_ID, 'qty': 3, 'price': 20.0}],
        )

        self._ingest_refunds_and_returns(order, parsed)
        self.assertEqual(len(order.external_return_ids), 1)
        self.assertEqual(len(order.external_refund_ids), 1)

        self._ingest_refunds_and_returns(order, parsed)
        self.assertEqual(
            len(order.external_return_ids), 1,
            'Duplicate synthetic return created on re-ingestion',
        )
        self.assertEqual(len(order.external_refund_ids), 1)

        # The refund's linked_return_id resolves to the synthetic return.
        synthetic_return = order.external_return_ids
        self.assertEqual(
            synthetic_return.external_str_id, self._R1674_SYNTHETIC_RETURN_ID,
        )
        self.assertTrue(
            synthetic_return.restocked_externally,
            'restocked_externally must round-trip through ingestion',
        )
        self.assertEqual(
            order.external_refund_ids.linked_return_id, synthetic_return,
            'Refund must resolve linked_return_id to the synthetic return',
        )


@tagged('post_install', '-at_install', 'test_shopify_refund_return_ingestion')
class TestShopifyReturnsRefundsDisabled(IntegrationShopifyBase):
    """The upgrade path: a store that has never enabled Returns & Refunds sync.

    Reading Shopify Return data needs the read_returns access scope, which such a store has no
    reason to have granted. With the switch off the connector must not ask for that data, and
    must not invent records out of data it never fetched.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration.write({
            'enable_returns_refunds_sync': False,
        })

    def _order_from_fixture(self, filename):
        order_data = _load_fixture(filename)['data']['order']
        order = self.adapter.gql.Order.set(**order_data)
        order.update_props(use_customer_currency=False)
        return order

    def test_query_body_omits_refunds_and_returns(self):
        """The order query must not request data the store cannot grant access to."""
        body = self.adapter.gql.Order.default_body()

        self.assertNotIn('returns(first: 10)', body)
        self.assertNotIn('refunds(first: 10)', body)

    def test_query_body_requests_refunds_and_returns_when_enabled(self):
        """Guards the switch itself: with sync on, the same body asks for both connections.

        Without this, `test_query_body_omits_refunds_and_returns` would still pass if the
        fields were dropped unconditionally.
        """
        self.integration.write({'enable_returns_refunds_sync': True})
        body = self.adapter.gql.Order.default_body()

        self.assertIn('returns(first: 10)', body)
        self.assertIn('refunds(first: 10)', body)

    def test_return_status_never_requested(self):
        """`returnStatus` is Return data no code reads. It belongs in neither variant."""
        self.assertNotIn('returnStatus', self.adapter.gql.Order.default_body())

        self.integration.write({'enable_returns_refunds_sync': True})
        self.assertNotIn('returnStatus', self.adapter.gql.Order.default_body())

    def test_restock_refund_synthesizes_nothing_when_disabled(self):
        """The regression this whole change exists to prevent.

        Order #1674 carries a refund line with restockType=RETURN and no Return entity. With
        the refund body left out of the query, `Refund.linked_return` reads falsy for every
        refund, which would flip `synthesizes_return` to True and fabricate a return that does
        not exist. Parsing must yield nothing at all instead.
        """
        order = self._order_from_fixture('order1674-refund-restock-no-return.json')

        self.assertEqual(
            order.parse_returns(), [],
            'A refund must never synthesize a return when returns sync is off',
        )
        self.assertEqual(
            order.parse_refunds(), [],
            'Refunds must not be parsed when returns & refunds sync is off',
        )

    def test_same_payload_does_synthesize_when_enabled(self):
        """Pairs with the test above so it cannot pass vacuously: the very same fixture must
        still synthesize exactly one return once the switch is on."""
        self.integration.write({'enable_returns_refunds_sync': True})
        order = self._order_from_fixture('order1674-refund-restock-no-return.json')

        returns = order.parse_returns()
        self.assertEqual(len(returns), 1)
        self.assertTrue(returns[0]['external_str_id'].startswith('refund-'))
        self.assertEqual(len(order.parse_refunds()), 1)

    def test_no_external_records_created_when_disabled(self):
        """End to end: the empty parse results must leave no external records behind."""
        order_data = _load_fixture('order1674-refund-restock-no-return.json')['data']['order']
        gql_order = self.adapter.gql.Order.set(**order_data)
        gql_order.update_props(use_customer_currency=False)

        sale_order = self.env['sale.order'].with_company(self.company).create({
            'partner_id': self.env['res.partner'].with_company(self.company).create({
                'name': 'Returns Disabled Customer',
            }).id,
            'integration_id': self.integration.id,
        })

        sale_order._apply_values_from_external({
            'order_returns': gql_order.parse_returns(),
            'order_refunds': gql_order.parse_refunds(),
        })

        self.assertFalse(sale_order.external_return_ids)
        self.assertFalse(sale_order.external_refund_ids)
