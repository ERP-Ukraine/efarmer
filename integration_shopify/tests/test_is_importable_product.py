# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.integration.tests.config.integration_init import OdooIntegrationInit, load_xml


@tagged('post_install', '-at_install')
class TestIsImportableProductShopify(OdooIntegrationInit):
    """Test is_importable_product method for Shopify integration."""

    @classmethod
    def setUpClass(cls):
        super(TestIsImportableProductShopify, cls).setUpClass()
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        company_id_1 = cls.env.ref('integration.test_integration_company_1')
        cls.integration = cls.env['sale.integration'].create({
            'name': 'Test Shopify Integration',
            'type_api': 'shopify',
            'company_id': company_id_1.id,
        })

    def test_no_filter_returns_true(self):
        """Empty filter should allow all products."""
        self.integration.set_settings_value('import_products_filter', '')

        result = self.integration.is_importable_product({'status': 'draft'})
        self.assertTrue(result)

    def test_status_filter_allows_matching_product(self):
        """Product with matching status should pass the filter."""
        self.integration.set_settings_value(
            'import_products_filter', '{"status": "active"}',
        )

        self.assertTrue(self.integration.is_importable_product({'status': 'active'}))

    def test_status_filter_rejects_non_matching_product(self):
        """Product with non-matching status should be filtered out."""
        self.integration.set_settings_value(
            'import_products_filter', '{"status": "active"}',
        )

        self.assertFalse(self.integration.is_importable_product({'status': 'draft'}))

    def test_comma_separated_values(self):
        """Comma-separated values in the filter should allow any listed value."""
        self.integration.set_settings_value(
            'import_products_filter', '{"status": "active,draft"}',
        )

        self.assertTrue(self.integration.is_importable_product({'status': 'active'}))
        self.assertTrue(self.integration.is_importable_product({'status': 'draft'}))
        self.assertFalse(self.integration.is_importable_product({'status': 'archived'}))

    def test_missing_key_in_product_data_rejects(self):
        """Product missing a filtered key should be rejected."""
        self.integration.set_settings_value(
            'import_products_filter', '{"status": "active"}',
        )

        self.assertFalse(self.integration.is_importable_product({'title': 'Test'}))
