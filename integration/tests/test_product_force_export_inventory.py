# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_product_force_export_inventory')
class TestProductForceExportInventory(OdooIntegrationInit):
    """The "Export Stock to Stores" action sends stock only to stores with stock synchronization turned on."""

    def setUp(self):
        super().setUp()

        self.store_on = self.integration_no_api_1
        self.store_off = self.integration_no_api_2

        self.store_on.export_inventory_job_enabled = True
        self.store_off.export_inventory_job_enabled = False
        self._set_scheduled_sync(self.store_on, False)
        self._set_scheduled_sync(self.store_off, False)

        self.product = self.product_pp_1
        self.product.integration_ids = self.store_on | self.store_off

    def _set_scheduled_sync(self, integration, active):
        self.assertTrue(integration.inventory_synchronization_cron_id, 'The store has no inventory cron')
        integration.inventory_synchronization_cron_id.active = active

    def _inventory_jobs(self, integration):
        return self.env['queue.job'].search([
            ('integration_id', '=', integration.id),
            ('method_name', '=', 'export_inventory'),
        ])

    def _notification(self, action):
        self.assertEqual(action['tag'], 'display_notification')
        return action['params']

    def test_store_with_stock_sync_off_is_skipped(self):
        """Store A (sync on) gets a job, store B (both syncs off) does not and is named in the warning."""
        action = self.product.action_force_export_inventory()

        self.assertEqual(len(self._inventory_jobs(self.store_on)), 1)
        self.assertFalse(self._inventory_jobs(self.store_off))

        params = self._notification(action)
        self.assertEqual(params['type'], 'warning')
        self.assertIn(self.store_off.name, params['message'])
        self.assertNotIn(self.store_on.name, params['message'])

    def test_scheduled_sync_alone_is_enough(self):
        """A store with only the scheduled sync turned on still receives a manual export."""
        self._set_scheduled_sync(self.store_off, True)

        action = self.product.action_force_export_inventory()

        self.assertEqual(len(self._inventory_jobs(self.store_on)), 1)
        self.assertEqual(len(self._inventory_jobs(self.store_off)), 1)
        self.assertEqual(self._notification(action)['type'], 'success')

    def test_real_time_sync_alone_is_enough(self):
        """A store with only the real-time sync turned on receives a manual export."""
        self.store_off.export_inventory_job_enabled = True

        self.product.action_force_export_inventory()

        self.assertEqual(len(self._inventory_jobs(self.store_off)), 1)

    def test_no_jobs_gives_a_warning_not_a_success(self):
        """When every store is skipped the user is told nothing was queued."""
        self.store_on.export_inventory_job_enabled = False

        action = self.product.action_force_export_inventory()

        self.assertFalse(self._inventory_jobs(self.store_on))
        self.assertFalse(self._inventory_jobs(self.store_off))

        params = self._notification(action)
        self.assertEqual(params['type'], 'warning')
        self.assertIn(self.store_on.name, params['message'])
        self.assertIn(self.store_off.name, params['message'])
        self.assertNotIn('are created', params['message'])

    def test_no_linked_store_gives_a_warning(self):
        """A product linked to no store creates no job and the user is told so."""
        self.product.integration_ids = False

        action = self.product.action_force_export_inventory()

        self.assertFalse(self._inventory_jobs(self.store_on))
        params = self._notification(action)
        self.assertEqual(params['type'], 'warning')
        self.assertNotIn('are created', params['message'])

    def test_unlinked_store_with_sync_off_is_not_reported(self):
        """A store the product is not linked to is neither exported to nor mentioned as skipped."""
        self.product.integration_ids = self.store_on

        action = self.product.action_force_export_inventory()

        self.assertEqual(len(self._inventory_jobs(self.store_on)), 1)
        params = self._notification(action)
        self.assertEqual(params['type'], 'success')
        self.assertNotIn(self.store_off.name, params['message'])

    def test_export_inventory_now_ignores_the_sync_flags(self):
        """The store-level "Export Inventory Now" button keeps working for a store with both syncs off."""
        self.product.integration_ids = self.store_off

        self.store_off.integrationApiExportInventory()

        self.assertEqual(len(self._inventory_jobs(self.store_off)), 1)
