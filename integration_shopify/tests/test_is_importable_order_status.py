# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from odoo.addons.integration.tests.config.integration_init import OdooIntegrationInit, load_xml


@tagged('post_install', '-at_install')
class TestIsImportableOrderStatusShopify(OdooIntegrationInit):
    """Test is_importable_order_status method for Shopify integration."""

    @classmethod
    def setUpClass(cls):
        super(TestIsImportableOrderStatusShopify, cls).setUpClass()
        # Load base integration XML data first (needed for refs)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        company_id_1 = cls.env.ref('integration.test_integration_company_1')
        cls.shopify_integration = cls.env['sale.integration'].create({
            'name': 'Test Shopify Integration',
            'type_api': 'shopify',
            'company_id': company_id_1.id,
        })
        # Clear the default status settings to avoid default values
        cls.shopify_integration.set_settings_value('receive_order_financial_statuses', '')
        cls.shopify_integration.set_settings_value('receive_order_fulfillment_statuses', '')

    def test_shopify_empty_filters_raises_validation_error(self):
        """Test Shopify integration with empty filters raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            self.shopify_integration.is_importable_order_status(['paid', 'fulfilled'])

        self.assertIn("Financial status filter is not configured", str(context.exception))

    def test_shopify_financial_status_only_raises_validation_error(self):
        """Test Shopify integration with financial status only raises ValidationError."""
        self.shopify_integration.set_settings_value('receive_order_financial_statuses', 'paid')

        with self.assertRaises(ValidationError) as context:
            self.shopify_integration.is_importable_order_status(['paid', 'fulfilled'])

        self.assertIn("Fulfillment status filter is not configured", str(context.exception))

    def test_shopify_fulfillment_status_only_raises_validation_error(self):
        """Test Shopify integration with fulfillment status only raises ValidationError."""
        self.shopify_integration.set_settings_value('receive_order_fulfillment_statuses', 'fulfilled')

        with self.assertRaises(ValidationError) as context:
            self.shopify_integration.is_importable_order_status(['paid', 'fulfilled'])

        self.assertIn("Financial status filter is not configured", str(context.exception))

    def test_shopify_both_statuses_required(self):
        """Test Shopify integration requires both statuses to match."""
        self.shopify_integration.set_settings_value('receive_order_financial_statuses', 'paid')
        self.shopify_integration.set_settings_value('receive_order_fulfillment_statuses', 'fulfilled')

        result = self.shopify_integration.is_importable_order_status(['paid', 'fulfilled'])
        self.assertTrue(result)

        result = self.shopify_integration.is_importable_order_status(['pending', 'fulfilled'])
        self.assertFalse(result)

        result = self.shopify_integration.is_importable_order_status(['paid', 'unfulfilled'])
        self.assertFalse(result)
