# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install')
class TestIntegrationEnabledProperties(OdooIntegrationInit):
    """Test enabled properties for integration features."""

    def setUp(self):
        super().setUp()
        # Create a base integration for testing
        self.integration = self.env['sale.integration'].create({
            'name': 'Test Integration',
            'type_api': 'no_api',
            'company_id': self.company_id_1.id,
            'state': 'active',
            'export_inventory_job_enabled': True,
            'export_template_job_enabled': True,
            'export_tracking_job_enabled': True,
            'export_sale_order_status_job_enabled': True,
        })

    def test_is_order_import_enabled(self):
        """Test is_order_import_enabled property in all scenarios."""
        # Test: returns True when integration is active and import is enabled
        self.integration.state = 'active'
        self.integration.receive_orders_cron_id_active = True
        self.assertTrue(self.integration.is_order_import_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.receive_orders_cron_id_active = True
        self.assertFalse(self.integration.is_order_import_enabled)

        # Test: returns False when import is disabled (even if active)
        self.integration.state = 'active'
        self.integration.receive_orders_cron_id_active = False
        self.assertFalse(self.integration.is_order_import_enabled)

    def test_is_periodic_inventory_sync_enabled(self):
        """Test is_periodic_inventory_sync_enabled property in all scenarios."""
        # Test: returns True when integration is active and sync is enabled
        self.integration.state = 'active'
        self.integration.inventory_synchronization_cron_id_active = True
        self.assertTrue(self.integration.is_periodic_inventory_sync_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.inventory_synchronization_cron_id_active = True
        self.assertFalse(self.integration.is_periodic_inventory_sync_enabled)

        # Test: returns False when sync is disabled (even if active)
        self.integration.state = 'active'
        self.integration.inventory_synchronization_cron_id_active = False
        self.assertFalse(self.integration.is_periodic_inventory_sync_enabled)

    def test_is_real_time_inventory_export_enabled(self):
        """Test is_real_time_inventory_export_enabled property in all scenarios."""
        # Test: returns True when integration is active and export is enabled
        self.integration.state = 'active'
        self.integration.export_inventory_job_enabled = True
        self.assertTrue(self.integration.is_real_time_inventory_export_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.export_inventory_job_enabled = True
        self.assertFalse(self.integration.is_real_time_inventory_export_enabled)

        # Test: returns False when export is disabled (even if active)
        self.integration.state = 'active'
        self.integration.export_inventory_job_enabled = False
        self.assertFalse(self.integration.is_real_time_inventory_export_enabled)

    def test_is_product_template_export_enabled(self):
        """Test is_product_template_export_enabled property in all scenarios."""
        # Test: returns True when integration is active and export is enabled
        self.integration.state = 'active'
        self.integration.export_template_job_enabled = True
        self.assertTrue(self.integration.is_product_template_export_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.export_template_job_enabled = True
        self.assertFalse(self.integration.is_product_template_export_enabled)

        # Test: returns False when export is disabled (even if active)
        self.integration.state = 'active'
        self.integration.export_template_job_enabled = False
        self.assertFalse(self.integration.is_product_template_export_enabled)

    def test_is_order_tracking_export_enabled(self):
        """Test is_order_tracking_export_enabled property in all scenarios."""
        # Test: returns True when integration is active and export is enabled
        self.integration.state = 'active'
        self.integration.export_tracking_job_enabled = True
        self.assertTrue(self.integration.is_order_tracking_export_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.export_tracking_job_enabled = True
        self.assertFalse(self.integration.is_order_tracking_export_enabled)

        # Test: returns False when export is disabled (even if active)
        self.integration.state = 'active'
        self.integration.export_tracking_job_enabled = False
        self.assertFalse(self.integration.is_order_tracking_export_enabled)

    def test_is_sale_order_status_export_enabled(self):
        """Test is_sale_order_status_export_enabled property in all scenarios."""
        # Test: returns True when integration is active and export is enabled
        self.integration.state = 'active'
        self.integration.export_sale_order_status_job_enabled = True
        self.assertTrue(self.integration.is_sale_order_status_export_enabled)

        # Test: returns False when integration is inactive
        self.integration.state = 'draft'
        self.integration.export_sale_order_status_job_enabled = True
        self.assertFalse(self.integration.is_sale_order_status_export_enabled)

        # Test: returns False when export is disabled (even if active)
        self.integration.state = 'active'
        self.integration.export_sale_order_status_job_enabled = False
        self.assertFalse(self.integration.is_sale_order_status_export_enabled)

    def test_all_properties_false_when_integration_inactive(self):
        """Test all properties return False when integration is inactive, regardless of individual settings."""
        self.integration.state = 'draft'
        # Set all flags to True
        self.integration.receive_orders_cron_id_active = True
        self.integration.inventory_synchronization_cron_id_active = True
        self.integration.export_inventory_job_enabled = True
        self.integration.export_template_job_enabled = True
        self.integration.export_tracking_job_enabled = True
        self.integration.export_sale_order_status_job_enabled = True

        # All should be False because integration is inactive
        self.assertFalse(self.integration.is_order_import_enabled)
        self.assertFalse(self.integration.is_periodic_inventory_sync_enabled)
        self.assertFalse(self.integration.is_real_time_inventory_export_enabled)
        self.assertFalse(self.integration.is_product_template_export_enabled)
        self.assertFalse(self.integration.is_order_tracking_export_enabled)
        self.assertFalse(self.integration.is_sale_order_status_export_enabled)
