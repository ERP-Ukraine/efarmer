# See LICENSE file for full copyright and licensing details.

import importlib.util

from odoo.tests import tagged
from odoo.tools import file_path

from .init_integration_shopify import IntegrationShopifyBase


@tagged('post_install', '-at_install')
class TestShopifyOriginalUrlFill(IntegrationShopifyBase):
    """The upgrade queues a job per integration that fills `original_url`; the job asks Shopify, not the migration."""

    def _migrate(self):
        # The migration file name has a hyphen, so it cannot be imported by name
        spec = importlib.util.spec_from_file_location(
            'post_migrate_fill_original_url',
            file_path('integration_shopify/migrations/19.0.2.3.2/post-migrate.py'),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.2.3.1')

    def _jobs(self):
        identity_key = f'fill_original_url-shopify_{self.integration.id}'

        return self.env['queue.job'].search([('identity_key', '=', identity_key)])

    def _original_url(self):
        return self.integration.get_settings_value('original_url')

    def test_job_stores_the_myshopify_domain_of_the_shop(self):
        self.integration.set_settings_value('original_url', '')

        self.integration.fill_original_url()

        self.assertEqual(self._original_url(), 'vendevstore2.myshopify.com')

    def test_migration_queues_a_job_without_asking_shopify(self):
        self.integration.set_settings_value('original_url', '')

        self._migrate()

        self.assertEqual(len(self._jobs()), 1)
        self.assertEqual(self._jobs().method_name, 'fill_original_url')
        # Only the job asks Shopify, so the value stays empty until it runs
        self.assertFalse(self._original_url())

    def test_migration_skips_integrations_that_have_original_url(self):
        self.integration.set_settings_value('original_url', 'vendevstore2.myshopify.com')

        self._migrate()

        self.assertFalse(self._jobs())

    def test_migration_skips_inactive_integrations(self):
        self.integration.set_settings_value('original_url', '')
        self.integration.write({'state': 'draft'})

        self._migrate()

        self.assertFalse(self._jobs())

    def test_migration_does_not_queue_the_same_job_twice(self):
        self.integration.set_settings_value('original_url', '')

        self._migrate()
        self._migrate()

        self.assertEqual(len(self._jobs()), 1)
