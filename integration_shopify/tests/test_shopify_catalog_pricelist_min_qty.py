# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'test_shopify_catalog_pricelist_min_qty')
class TestShopifyCatalogPricelistMinQty(TransactionCase):
    """Catalog price is the price of one unit, the same as the Odoo eCommerce shows on the website."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration = cls.env['sale.integration'].create({'name': 'Catalog Test', 'type_api': 'no_api'})
        cls.variant = cls.env['product.product'].create({'name': 'Catalog Variant', 'list_price': 100.0})

    def _create_pricelist(self, name, *rules):
        """Create a pricelist with fixed-price rules for the test variant, each rule given as (min_qty, price)."""
        return self.env['product.pricelist'].create({
            'name': name,
            'item_ids': [(0, 0, {
                'applied_on': '1_product',
                'product_tmpl_id': self.variant.product_tmpl_id.id,
                'compute_price': 'fixed',
                'fixed_price': price,
                'min_quantity': min_qty,
            }) for min_qty, price in rules],
        })

    def _create_line(self, pricelist, pricelist_compare_at=None):
        return self.env['integration.catalog.external.line'].create({
            'integration_id': self.integration.id,
            'pricelist_id': pricelist.id,
            'pricelist_compare_at_id': pricelist_compare_at.id if pricelist_compare_at else False,
        })

    def test_rule_with_min_qty_one_is_applied(self):
        line = self._create_line(self._create_pricelist('Min Qty 1', (1, 80.0)))

        price, compare_at_price = line._prepare_prices(self.variant)

        self.assertEqual(price, 80.0)
        self.assertIsNone(compare_at_price)

    def test_rule_with_min_qty_zero_is_applied(self):
        line = self._create_line(self._create_pricelist('Min Qty 0', (0, 90.0)))

        price, compare_at_price = line._prepare_prices(self.variant)

        self.assertEqual(price, 90.0)
        self.assertIsNone(compare_at_price)

    def test_wholesale_rule_does_not_win_for_one_unit(self):
        line = self._create_line(self._create_pricelist('Mixed', (0, 90.0), (1, 80.0), (10, 50.0)))

        price, _compare_at_price = line._prepare_prices(self.variant)

        self.assertEqual(price, 80.0)

    def test_only_wholesale_rules_exclude_the_product(self):
        line = self._create_line(self._create_pricelist('Wholesale Only', (5, 60.0), (10, 50.0)))

        price, compare_at_price = line._prepare_prices(self.variant)

        self.assertIsNone(price)
        self.assertIsNone(compare_at_price)

    def test_compare_at_rule_with_min_qty_one_is_applied(self):
        line = self._create_line(
            self._create_pricelist('Price', (1, 80.0)),
            self._create_pricelist('Compare At', (1, 120.0)),
        )

        price, compare_at_price = line._prepare_prices(self.variant)

        self.assertEqual(price, 80.0)
        self.assertEqual(compare_at_price, 120.0)

    def test_compare_at_with_only_wholesale_rules_is_empty(self):
        line = self._create_line(
            self._create_pricelist('Price', (1, 80.0)),
            self._create_pricelist('Compare At Wholesale', (5, 120.0)),
        )

        price, compare_at_price = line._prepare_prices(self.variant)

        self.assertEqual(price, 80.0)
        self.assertIsNone(compare_at_price)
