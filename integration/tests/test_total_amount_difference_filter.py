# See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestTotalAmountDifferenceFilter(OdooIntegrationInit):
    """The "Total Mismatch with Store" filter must find exactly the orders that show the warning on the form:
    an order of an E-Commerce Store, with an amount from the store, which differs from the Odoo amount.
    """

    FILTER_NAME = 'total_amount_difference'

    def setUp(self):
        super(TestTotalAmountDifferenceFilter, self).setUp()
        self.integration = self.integration_no_api_1
        self.partner = self.env['res.partner'].create({'name': 'Mismatch Customer'})
        self.product = self.env['product.product'].create({
            'name': 'Mismatch Product',
            'list_price': 10.0,
            'taxes_id': [(5, 0, 0)],
        })
        self.SaleOrder = self.env['sale.order']

        self.order_mismatch = self._create_order(integration_amount_total=15.0)
        self.order_same = self._create_order(integration_amount_total=10.0)
        self.order_no_store_amount = self._create_order(integration_amount_total=0.0)
        self.order_rounding_only = self._create_order(integration_amount_total=10.004)
        self.order_cent_off = self._create_order(integration_amount_total=10.01)
        self.order_not_from_store = self._create_order(integration_amount_total=15.0, integration=False)
        self.orders = (
            self.order_mismatch
            + self.order_same
            + self.order_no_store_amount
            + self.order_rounding_only
            + self.order_cent_off
            + self.order_not_from_store
        )

    def _create_order(self, integration_amount_total, integration=True):
        order = self.SaleOrder.with_context(skip_dispatch_to_external=True).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id if integration else False,
            'integration_amount_total': integration_amount_total,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 10.0,
            })],
        })
        # Re-browse for a clean context: the create-time `skip_dispatch_to_external` otherwise sticks to the handle
        return self.SaleOrder.browse(order.id)

    def _filter_domain(self, view_xmlid):
        view = self.env.ref(view_xmlid)
        arch = self.SaleOrder.get_view(view_id=view.id, view_type='search')['arch']
        filters = etree.fromstring(arch).xpath('//filter[@name="%s"]' % self.FILTER_NAME)
        self.assertEqual(len(filters), 1, 'Filter is expected exactly once in %s' % view_xmlid)
        return filters[0].get('domain')

    def _found_by_filter(self, view_xmlid):
        domain = self._filter_domain(view_xmlid)
        found = self.SaleOrder.search([('id', 'in', self.orders.ids)] + eval(domain, {'uid': self.env.uid}))
        return found

    def test_search_by_computed_field(self):
        found = self.SaleOrder.search([
            ('id', 'in', self.orders.ids),
            ('is_total_amount_difference', '=', True),
        ])
        self.assertEqual(found, self.order_mismatch + self.order_cent_off + self.order_not_from_store)

    def test_search_by_computed_field_negated(self):
        expected = self.orders - (self.order_mismatch + self.order_cent_off + self.order_not_from_store)

        for operator, value in (('=', False), ('!=', True)):
            found = self.SaleOrder.search([
                ('id', 'in', self.orders.ids),
                ('is_total_amount_difference', operator, value),
            ])
            self.assertEqual(found, expected, 'Operator %s %s' % (operator, value))

    def test_search_matches_compute(self):
        found = self.SaleOrder.search([
            ('id', 'in', self.orders.ids),
            ('is_total_amount_difference', '=', True),
        ])
        self.assertEqual(found, self.orders.filtered('is_total_amount_difference'))

    def test_filter_finds_orders_with_warning(self):
        warned = self.orders.filtered(
            lambda order: order.integration_id and order.is_total_amount_difference
        )
        self.assertEqual(warned, self.order_mismatch + self.order_cent_off)

        for view_xmlid in (
            'sale.view_sales_order_filter',
            'sale.sale_order_view_search_inherit_quotation',
            'sale.sale_order_view_search_inherit_sale',
        ):
            self.assertEqual(self._found_by_filter(view_xmlid), warned, view_xmlid)

    def test_filter_skips_orders_without_store_amount_and_with_same_amount(self):
        found = self._found_by_filter('sale.view_sales_order_filter')

        self.assertNotIn(self.order_no_store_amount, found)
        self.assertNotIn(self.order_same, found)
        self.assertNotIn(self.order_rounding_only, found)

    def test_filter_skips_orders_not_from_store(self):
        found = self._found_by_filter('sale.view_sales_order_filter')

        self.assertNotIn(self.order_not_from_store, found)

    def test_filter_follows_amount_changes(self):
        self.assertIn(self.order_mismatch, self._found_by_filter('sale.view_sales_order_filter'))

        self.order_mismatch.integration_amount_total = self.order_mismatch.amount_total

        self.assertNotIn(self.order_mismatch, self._found_by_filter('sale.view_sales_order_filter'))
