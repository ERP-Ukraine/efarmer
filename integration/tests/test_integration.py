# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestIntegration(OdooIntegrationInit):
    """Tests for the link-vs-push contract.

    - Linking a product to a store (or creating it linked) never pushes.
    - Automatic export only updates products that are ALREADY mapped in a store, gated by
      `export_template_job_enabled` and `allow_export_images`.
    - The explicit "Export to Stores" action (`action_export_to_stores`) always pushes, ignoring the toggle.
    """

    def setUp(self):
        super(TestIntegration, self).setUp()

    def reload(self, product):
        # Records returned by create() keep create-time context flags (`skip_product_export`, `from_product_create`)
        # that suppress the write-triggered export. Re-browse to get the clean context a user has when editing a
        # product loaded from the database — that is the behaviour we want to test.
        return self.env[product._name].browse(product.id)

    # --- Linking / creating never pushes ------------------------------------------------------------------

    def test_no_export_job_on_create(self):
        integration = self.integration_no_api_1
        self.make_field_tracked(integration)

        vals = self.generate_product_data(name='fresh', integration=integration)
        product = self.env['product.template'].create(vals)

        # The product is linked, but creating it never queues an export job.
        self.assertEqual(product.integration_ids, integration)
        for export_images in (True, False):
            key = self.get_integration_identity_key(integration, product, export_images=export_images)
            self.assertFalse(self.get_queue_job(key))

    def test_no_export_job_on_write_unmapped(self):
        # A product linked to a store but never published (not mapped) must not be pushed when edited.
        integration = self.integration_no_api_1
        self.make_field_tracked(integration)

        vals = self.generate_product_data(name='unmapped', integration=integration)
        product = self.env['product.template'].with_context(skip_product_export=True).create(vals)

        self.reload(product).write({'name': 'Renamed unmapped'})

        key = self.get_integration_identity_key(integration, product, export_images=False)
        self.assertFalse(self.get_queue_job(key))

    # --- Automatic change-driven export of an already-mapped product --------------------------------------

    def test_sync_job_on_write_mapped(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1  # already linked to and mapped in `integration`
        self.make_field_tracked(integration)

        self.reload(product).write({'name': 'Renamed mapped'})

        key = self.get_integration_identity_key(integration, product, export_images=False)
        self.assertTrue(self.get_queue_job(key))

    def test_export_template_job_enabled(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1
        self.make_field_tracked(integration)
        key = self.get_integration_identity_key(integration, product, export_images=False)

        # Toggle OFF -> the change-driven export does nothing.
        integration.export_template_job_enabled = False
        self.reload(product).write({'name': 'Renamed off'})
        self.assertFalse(self.get_queue_job(key))

        # Toggle ON -> a write to a mapped product queues a job.
        integration.export_template_job_enabled = True
        self.reload(product).write({'name': 'Renamed on'})
        self.assertTrue(self.get_queue_job(key))

    def test_allow_export_images(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1
        self.make_field_tracked(integration)
        image = self.generate_product_data(name='img')['image_1920']

        # allow_export_images = True -> the queued job carries images.
        integration.allow_export_images = True
        self.reload(product).write({'name': 'imgs on', 'image_1920': image})
        key_with_images = self.get_integration_identity_key(integration, product, export_images=True)
        self.assertTrue(self.get_queue_job(key_with_images))

        # allow_export_images = False -> the queued job is created without images.
        integration.allow_export_images = False
        self.reload(product).write({'name': 'imgs off', 'image_1920': image})
        key_without_images = self.get_integration_identity_key(integration, product, export_images=False)
        self.assertTrue(self.get_queue_job(key_without_images))

    def test_skip_product_export(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1
        self.make_field_tracked(integration)

        # Even on a mapped product, an explicit `skip_product_export` suppresses the export.
        self.reload(product).with_context(skip_product_export=True).write({'name': 'Skipped'})

        key = self.get_integration_identity_key(integration, product, export_images=False)
        self.assertFalse(self.get_queue_job(key))

    def test_company_id(self):
        integrations = self.get_all_integrations()

        # A product linked to and mapped in both integrations (each in a different company).
        vals = self.generate_product_data(name='both', integration=integrations)
        product = self.env['product.template'].with_context(skip_product_export=True).create(vals)
        self.map_product(product, self.integration_no_api_1, 'COMP-1')
        self.map_product(product, self.integration_no_api_2, 'COMP-2')
        for integration in integrations:
            self.make_field_tracked(integration)

        self.reload(product).write({'name': 'Renamed both'})

        # One job per integration, each carrying that integration's company.
        for integration in integrations:
            key = self.get_integration_identity_key(integration, product, export_images=False)
            job = self.get_queue_job(key)
            self.assertTrue(job)
            self.assertEqual(job.company_id, integration.company_id)

    # --- Explicit push ("Export to Stores") -------------------------------------------------------------

    def test_explicit_export_creates_job(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1

        self.reload(product).action_export_to_stores()

        key = self.get_integration_identity_key(integration, product, export_images=True, force=True)
        self.assertTrue(self.get_queue_job(key))

    def test_explicit_export_ignores_job_toggle(self):
        integration = self.integration_no_api_1
        product = self.product_pt_1

        # Even with the automatic export job disabled, an explicit push still runs.
        integration.export_template_job_enabled = False
        self.reload(product).action_export_to_stores()

        key = self.get_integration_identity_key(integration, product, export_images=True, force=True)
        self.assertTrue(self.get_queue_job(key))

    def test_mandatory_fields_initial_product_export(self):
        # An explicit export of a product missing a mandatory field still queues a job (which fails later to
        # alert the user), rather than silently doing nothing.
        integration = self.integration_no_api_1
        vals = self.generate_product_data(name='no-ref', integration=integration)
        vals.update({'default_code': False})
        product = self.env['product.template'].with_context(skip_product_export=True).create(vals)
        self.assertFalse(product.default_code)

        self.reload(product).action_export_to_stores()

        key = self.get_integration_identity_key(integration, product, export_images=True, force=True)
        self.assertTrue(self.get_queue_job(key))
