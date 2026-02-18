# See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo.tests import tagged
from odoo.tests.common import mute_logger


from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install')
class TestIsImportableOrderDate(OdooIntegrationInit):
    """Test is_importable_order_date method for base integration."""

    def setUp(self):
        super().setUp()
        # Create a base integration for testing
        self.base_integration = self.env['sale.integration'].create({
            'name': 'Test Base Integration',
            'type_api': 'no_api',
            'company_id': self.company_id_1.id,
        })

    def test_empty_date_returns_true(self):
        """Test that when date is empty/None, method returns True."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Test with None
        result = self.base_integration.is_importable_order_date(None)
        self.assertTrue(result)

        # Test with empty string
        result = self.base_integration.is_importable_order_date('')
        self.assertTrue(result)

    def test_order_after_cut_off_date_returns_true(self):
        """Test that order created after cut-off date returns True."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order created after cut-off date
        result = self.base_integration.is_importable_order_date('2025-11-07T10:23:54')
        self.assertTrue(result)

    def test_order_before_cut_off_date_returns_false(self):
        """Test that order created before cut-off date returns False."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order created before cut-off date
        result = self.base_integration.is_importable_order_date('2025-06-25T10:55:51')
        self.assertFalse(result)

    def test_order_on_cut_off_date_returns_true(self):
        """Test that order created exactly on cut-off date returns True."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order created exactly on cut-off date
        result = self.base_integration.is_importable_order_date('2025-10-01T00:00:00')
        self.assertTrue(result)

    def test_iso_format_with_timezone(self):
        """Test ISO format with timezone (Shopify format)."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Shopify format with timezone
        result = self.base_integration.is_importable_order_date('2025-06-12T15:42:12+02:00')
        # Should be converted to UTC and compared
        self.assertFalse(result)  # Before cut-off date

    def test_sql_datetime_format(self):
        """Test SQL datetime format (PrestaShop/Magento2 format)."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # PrestaShop format (space-separated)
        result = self.base_integration.is_importable_order_date('2025-10-08 15:59:31')
        self.assertTrue(result)  # After cut-off date

        # Magento2 format (space-separated)
        result = self.base_integration.is_importable_order_date('2025-06-25 10:55:51')
        self.assertFalse(result)  # Before cut-off date

    def test_invalid_date_format_returns_true(self):
        """Test that invalid date format returns True (graceful failure)."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Invalid date format should log warning but return True
        with mute_logger('odoo.addons.integration.models.sale_integration'):
            result = self.base_integration.is_importable_order_date('invalid-date-format')
            self.assertTrue(result)

    def test_all_connector_date_formats(self):
        """Test all connector-specific date formats."""
        cut_off_date = datetime(2025, 10, 1, 0, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        #
        # WooCommerce format
        #
        # 1. Order created after cut-off date
        result = self.base_integration.is_importable_order_date('2025-11-07T10:23:54')
        self.assertTrue(result)

        # 2. Order created before cut-off date
        result = self.base_integration.is_importable_order_date('2025-06-25T10:55:51')
        self.assertFalse(result)

        #
        # PrestaShop / Magento2 format
        #
        # 1. Order created after cut-off date
        result = self.base_integration.is_importable_order_date('2025-10-08 15:59:31')
        self.assertTrue(result)

        # 2. Order created before cut-off date
        result = self.base_integration.is_importable_order_date('2025-09-15 10:30:00')
        self.assertFalse(result)

        #
        # Shopify format with timezone
        #
        # 1. Order created after cut-off date
        result = self.base_integration.is_importable_order_date('2025-11-07T10:23:54+02:00')
        self.assertTrue(result)

        # 2. Order created before cut-off date
        result = self.base_integration.is_importable_order_date('2025-06-12T15:42:12+02:00')
        self.assertFalse(result)

    def test_edge_cases_exact_time_matching(self):
        """Test edge cases with exact time matching."""
        cut_off_date = datetime(2025, 10, 1, 12, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order exactly on cut-off date and time
        result = self.base_integration.is_importable_order_date('2025-10-01T12:00:00')
        self.assertTrue(result)

        # Order one second before cut-off time
        result = self.base_integration.is_importable_order_date('2025-10-01T11:59:59')
        self.assertFalse(result)

        # Order one second after cut-off time
        result = self.base_integration.is_importable_order_date('2025-10-01T12:00:01')
        self.assertTrue(result)

    def test_timezone_conversion_edge_cases(self):
        """Test timezone conversion with edge cases."""
        # Set cut-off date to 2025-10-01 13:00:00 UTC
        cut_off_date = datetime(2025, 10, 1, 13, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order at 2025-10-01 15:00:00+02:00 = 2025-10-01 13:00:00 UTC (exactly on cut-off)
        result = self.base_integration.is_importable_order_date('2025-10-01T15:00:00+02:00')
        self.assertTrue(result)

        # Order at 2025-10-01 14:59:59+02:00 = 2025-10-01 12:59:59 UTC (before cut-off)
        result = self.base_integration.is_importable_order_date('2025-10-01T14:59:59+02:00')
        self.assertFalse(result)

        # Order at 2025-10-01 15:00:01+02:00 = 2025-10-01 13:00:01 UTC (after cut-off)
        result = self.base_integration.is_importable_order_date('2025-10-01T15:00:01+02:00')
        self.assertTrue(result)

        # Test with different timezone offset
        cut_off_date = datetime(2025, 10, 1, 12, 0, 0)
        self.base_integration.orders_cut_off_datetime = cut_off_date

        # Order exactly on cut-off date and time (with timezone)
        result = self.base_integration.is_importable_order_date('2025-10-01T14:00:00+02:00')
        self.assertTrue(result)  # 14:00+02:00 = 12:00 UTC

        # Order one second before cut-off time
        result = self.base_integration.is_importable_order_date('2025-10-01T13:59:59+02:00')
        self.assertFalse(result)  # 13:59:59+02:00 = 11:59:59 UTC

        # Order one second after cut-off time
        result = self.base_integration.is_importable_order_date('2025-10-01T14:00:01+02:00')
        self.assertTrue(result)  # 14:00:01+02:00 = 12:00:01 UTC
