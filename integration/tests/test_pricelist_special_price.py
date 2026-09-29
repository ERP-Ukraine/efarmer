# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_pricelist_special_price')
class TestPricelistSpecialPrice(OdooIntegrationInit):

    def setUp(self):
        super().setUp()
        self.sale_pricelist = self.env.ref('integration.pricelist_1')
        self.integration_no_api_1.integration_sale_pricelist_id = self.sale_pricelist

        # The generic no_api test integration has no adapter settings. The positive
        # price path still uses the standard connector price formatting logic.
        self.env['sale.integration.api.field'].create({
            'name': 'decimal_precision',
            'value': '2',
            'sia_id': self.integration_no_api_1.id,
        })

    def test_no_matching_sale_pricelist_rule_returns_empty_price(self):
        # Odoo's pricelist engine falls back to the product's regular price when no rule matches.
        # The connector must not treat that fallback as a promotional price.
        for product in (self.product_pt_1, self.product_pt_1.product_variant_id):
            price, date_start, date_end = product.get_pricelist_special_price_data(
                self.integration_no_api_1.id,
            )

            self.assertEqual(price, '')
            self.assertEqual(date_start, '')
            self.assertEqual(date_end, '')

    def test_matching_sale_pricelist_rule_returns_rule_price(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.sale_pricelist.id,
            'applied_on': '1_product',
            'product_tmpl_id': self.product_pt_1.id,
            'compute_price': 'fixed',
            'fixed_price': 9.0,
        })

        price, date_start, date_end = self.product_pt_1.get_pricelist_special_price_data(
            self.integration_no_api_1.id,
        )

        self.assertEqual(price, 9.0)
        self.assertEqual(date_start, '')
        self.assertEqual(date_end, '')
