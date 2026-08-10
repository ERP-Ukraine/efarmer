# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestAutoExportNewProducts(OdooIntegrationInit):
    """Tests for "Auto-Export New Products".

    A store with `auto_export_new_products=True` auto-links new products and publishes them — but only once
    they satisfy that store's "Required Fields for Initial Export" (default: internal reference / SKU). Until
    ready, the product is recorded in `pending_export_integration_ids` and a warning is shown.
    """

    def setUp(self):
        super(TestAutoExportNewProducts, self).setUp()
        self.integration = self.integration_no_api_1
        self.integration.auto_export_new_products = True

    @property
    def Template(self):
        return self.env['product.template'].with_user(self.integration_administrator)

    def reload(self, product):
        # Records returned by create() keep create-time context flags that suppress the write hooks; re-browse to
        # behave like a product edited later by a user.
        return self.env[product._name].browse(product.id)

    def _export_key(self, product, export_images=True):
        # Auto-export uses the explicit push path (manual_trigger -> force=True).
        return self.get_integration_identity_key(self.integration, product, export_images=export_images, force=True)

    # 1. Ready product -> auto-linked AND exported, nothing pending.
    def test_ready_product_is_exported_on_create(self):
        vals = self.generate_product_data(name='ready', integration=self.integration)
        product = self.Template.create(vals)

        self.assertIn(self.integration, product.integration_ids)
        self.assertFalse(product.pending_export_integration_ids)
        self.assertTrue(self.get_queue_job(self._export_key(product)))

    # 2. Incomplete product -> linked, NOT exported, pending + warning.
    def test_incomplete_product_is_pending(self):
        vals = self.generate_product_data(name='incomplete', integration=self.integration)
        vals['default_code'] = False
        product = self.Template.create(vals)

        self.assertIn(self.integration, product.integration_ids)
        self.assertIn(self.integration, product.pending_export_integration_ids)
        self.assertFalse(self.get_queue_job(self._export_key(product, export_images=False)))
        self.assertFalse(self.get_queue_job(self._export_key(product, export_images=True)))
        self.assertTrue(product.pending_first_export_warning)

    # 3. Filling the required field later triggers the export and clears pending.
    def test_pending_product_exports_when_ready(self):
        vals = self.generate_product_data(name='later', integration=self.integration)
        vals['default_code'] = False
        product = self.Template.create(vals)
        self.assertIn(self.integration, product.pending_export_integration_ids)

        self.reload(product).write({'default_code': 'later_sku'})

        self.assertFalse(product.pending_export_integration_ids)
        self.assertTrue(self.get_queue_job(self._export_key(product)))

    # 4. Multi-variant: exports only once ALL variants satisfy the fields.
    def test_multi_variant_waits_for_all_variants(self):
        vals = self.generate_product_data(name='multi', integration=self.integration)
        vals['attribute_line_ids'] = [(0, 0, {
            'attribute_id': self.product_attribute_color.id,
            'value_ids': [(6, 0, self.product_attribute_color.value_ids.ids)],
        })]
        product = self.Template.create(vals)
        variants = product.product_variant_ids
        self.assertEqual(len(variants), 2)

        # generate_product_data put the same default_code on the template create, but variants need their own;
        # clear one to make the template not ready.
        variants.with_context(skip_product_export=True).write({'default_code': False})
        variants[0].with_context(skip_product_export=True).default_code = 'multi_a'
        self.reload(product)._process_pending_first_export()
        self.assertIn(self.integration, product.pending_export_integration_ids)  # still pending (variant[1] empty)

        self.reload(variants[1]).write({'default_code': 'multi_b'})
        self.assertFalse(product.pending_export_integration_ids)
        self.assertTrue(self.get_queue_job(self._export_key(product)))

    # 5. Only opt-in stores auto-export; other linked stores stay link-only.
    def test_only_opt_in_store_exports(self):
        other = self.integration_no_api_2  # auto_export_new_products stays False
        vals = self.generate_product_data(name='mixed', integration=self.integration | other)
        product = self.Template.create(vals)

        self.assertNotIn(other, product.pending_export_integration_ids)
        # opt-in store exported; non-opt-in store has no job.
        self.assertTrue(self.get_queue_job(self._export_key(product)))
        other_key = self.get_integration_identity_key(other, product, export_images=True, force=True)
        self.assertFalse(self.get_queue_job(other_key))

    # 6. Unlinking a pending store before it's ready cancels the pending export.
    def test_unlink_pending_store_cancels(self):
        vals = self.generate_product_data(name='unlinkme', integration=self.integration)
        vals['default_code'] = False
        product = self.Template.create(vals)
        self.assertIn(self.integration, product.pending_export_integration_ids)

        self.reload(product).write({'integration_ids': [(3, self.integration.id)]})

        self.assertFalse(product.pending_export_integration_ids)
        self.assertFalse(self.get_queue_job(self._export_key(product)))

    # 7. Default auto-linking: a product created without explicit stores links to opt-in stores.
    def test_default_links_to_opt_in_store(self):
        # Make our test store the only one opting in, so the default links deterministically regardless of any
        # other opt-in stores configured in this database. (sale.integration.write is single-record only.)
        for other in self.env['sale.integration'].search([('id', '!=', self.integration.id)]):
            other.auto_export_new_products = False

        vals = self.generate_product_data(name='defaultlink')
        del vals['integration_ids']  # no explicit integrations -> use the field default
        product = self.Template.create(vals)

        self.assertEqual(product.integration_ids, self.integration)

    # 8. skip_product_export (import/bulk path) must not auto-export.
    def test_skip_product_export_no_auto_export(self):
        vals = self.generate_product_data(name='imported', integration=self.integration)
        product = self.Template.with_context(skip_product_export=True).create(vals)

        self.assertFalse(product.pending_export_integration_ids)
        self.assertFalse(self.get_queue_job(self._export_key(product)))
