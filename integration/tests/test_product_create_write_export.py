# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.exceptions import UserError

from .config.integration_init import OdooIntegrationInit, load_xml


class TestErrorCreate(UserError):
    pass


class TestErrorWrite(UserError):
    pass


class TestErrorExportTemplate(UserError):
    pass


class TestErrorExportImage(UserError):
    pass


@tagged('post_install', '-at_install', 'test_integration_core')
class TestProductCreateWriteExport(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestProductCreateWriteExport, cls).setUpClass()
        # Load base integration XML data first (needed for refs)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )

        integration_no_api_1 = cls.env.ref('integration.integration_no_api_1')
        integration_no_api_2 = cls.env.ref('integration.integration_no_api_2')

        assert integration_no_api_1.is_active
        assert integration_no_api_2.is_active
        assert integration_no_api_1.export_template_job_enabled
        assert integration_no_api_2.export_template_job_enabled

    @property
    def skip_ctx(self):
        return dict(skip_product_export=True)

    @property
    def template(self):
        return self.env['product.template'].with_user(self.integration_administrator)

    @property
    def variant(self):
        return self.env['product.product'].with_user(self.integration_administrator)

    def _generate_attribute_lines(self):
        return [(0, 0, {
            'attribute_id': self.product_attribute_color.id,
            'value_ids': [(6, 0, self.product_attribute_color.value_ids.ids)],
        })]

    def _patch_export_methods(self):

        def _trigger_export_single_template_patch(*args, first_export=False):
            if first_export:
                raise TestErrorCreate('trigger-export-from-create-called')
            raise TestErrorWrite('trigger-export-from-write-called')

        self.patch(
            type(self.env['product.template']),
            '_trigger_export_single_template',
            _trigger_export_single_template_patch,
        )

    def test_create_simple_template_apply_integration(self):
        self._patch_export_methods()  # raise if skip_ctx doesnt't work

        # 1. Create template with one active integration
        vals = self.generate_product_data(
            name='product-1',
            integration=self.integration_no_api_1,
        )
        record = self.template.with_context(**self.skip_ctx).create(vals)

        self.assertTrue(record.integration_ids == self.integration_no_api_1)
        self.assertTrue(len(record.product_variant_ids) == 1)
        self.assertTrue(record.product_variant_ids.integration_ids == self.integration_no_api_1)

        # 2. Create template with two active integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-2',
            integration=integrations,
        )
        record = self.template.with_context(**self.skip_ctx).create(vals)

        self.assertTrue(record.integration_ids == integrations)
        self.assertTrue(len(record.product_variant_ids) == 1)
        self.assertTrue(record.product_variant_ids.integration_ids == integrations)

    def test_create_complex_template_apply_integration(self):
        self._patch_export_methods()  # raise if skip_ctx doesnt't work

        # 1. Create template with multiple variants and one integration
        vals = self.generate_product_data(
            name='product-1',
            integration=self.integration_no_api_1,
        )
        vals['attribute_line_ids'] = self._generate_attribute_lines()

        record = self.template.with_context(**self.skip_ctx).create(vals)

        self.assertFalse(record.integration_ids)
        self.assertTrue(len(record.product_variant_ids) == 2)
        self.assertTrue(record.product_variant_ids[0].integration_ids == self.integration_no_api_1)
        self.assertTrue(record.product_variant_ids[1].integration_ids == self.integration_no_api_1)

        # 1. Create template with multiple variants and two integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-2',
            integration=integrations,
        )
        vals['attribute_line_ids'] = self._generate_attribute_lines()

        record = self.template.with_context(**self.skip_ctx).create(vals)

        self.assertFalse(record.integration_ids)
        self.assertTrue(len(record.product_variant_ids) == 2)
        self.assertTrue(record.product_variant_ids[0].integration_ids == integrations)
        self.assertTrue(record.product_variant_ids[1].integration_ids == integrations)

    def test_create_variant_apply_integration(self):
        self._patch_export_methods()  # raise if skip_ctx doesnt't work

        # 1. Create variant with one active integration
        vals = self.generate_product_data(
            name='product-1',
            integration=self.integration_no_api_1,
        )
        record = self.variant.with_context(**self.skip_ctx).create(vals)

        self.assertTrue(record.integration_ids == self.integration_no_api_1)
        self.assertTrue(len(record.product_tmpl_id.product_variant_ids) == 1)
        self.assertTrue(record.product_tmpl_id.integration_ids == self.integration_no_api_1)

        # 2. Create variant with two active integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-2',
            integration=integrations,
        )
        record = self.variant.with_context(**self.skip_ctx).create(vals)

        self.assertTrue(record.integration_ids == integrations)
        self.assertTrue(len(record.product_tmpl_id.product_variant_ids) == 1)
        self.assertTrue(record.product_tmpl_id.integration_ids == integrations)

    def test_trigger_export_from_template_create(self):
        # Patch export methods
        self._patch_export_methods()  # expects raise

        vals = self.generate_product_data(
            name='product-1',
            integration=self.integration_no_api_1,
        )

        # 1. Create with one integration
        with self.assertRaises(TestErrorCreate):
            record = self.template.create(vals)

            self.assertTrue(record.integration_ids == self.integration_no_api_1)
            self.assertTrue(len(record.product_variant_ids) == 1)
            self.assertTrue(record.product_variant_ids.integration_ids == self.integration_no_api_1)

            self.assertTrue(record._get_enabled_integrations() == self.integration_no_api_1)

        # 2. Create with two integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-2',
            integration=integrations,
        )
        with self.assertRaises(TestErrorCreate):
            record = self.template.create(vals)

            self.assertTrue(record.integration_ids == integrations)
            self.assertTrue(len(record.product_variant_ids) == 1)
            self.assertTrue(record.product_variant_ids.integration_ids == integrations)

            self.assertTrue(record._get_enabled_integrations() == integrations)

    def test_trigger_export_from_variant_create(self):
        # Patch export methods
        self._patch_export_methods()  # expects raise

        vals = self.generate_product_data(
            name='product-1',
            integration=self.integration_no_api_1,
        )

        # 1. Create with one integration
        with self.assertRaises(TestErrorCreate):
            record = self.variant.create(vals)

            self.assertTrue(record.integration_ids == self.integration_no_api_1)
            self.assertTrue(len(record.product_variant_ids) == 1)
            self.assertTrue(record.product_variant_ids.integration_ids == self.integration_no_api_1)

            self.assertTrue(record._get_enabled_integrations() == self.integration_no_api_1)

        # 2. Create with two integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-2',
            integration=integrations,
        )
        with self.assertRaises(TestErrorCreate):
            record = self.variant.create(vals)

            self.assertTrue(record.integration_ids == integrations)
            self.assertTrue(len(record.product_variant_ids) == 1)
            self.assertTrue(record.product_variant_ids.integration_ids == integrations)

            self.assertTrue(record._get_enabled_integrations() == integrations)

    def test_get_related_valid_integrations(self):
        # 1. Create template with two integrations
        integrations = self.get_all_integrations()

        vals = self.generate_product_data(
            name='product-1',
            integration=integrations,
        )
        record = self.template.with_context(**self.skip_ctx).create(vals)

        self.assertTrue(record.integration_ids == integrations)
        self.assertTrue(len(record.product_variant_ids) == 1)
        self.assertTrue(record.product_variant_ids.integration_ids == integrations)

        # 2. Check
        self.assertEqual(record._get_enabled_integrations(), integrations)

        # 2.1
        self.integration_no_api_1.export_template_job_enabled = False

        self.assertEqual(record._get_enabled_integrations(), self.integration_no_api_2)

        # 2.2
        self.integration_no_api_1.export_template_job_enabled = True
        self.integration_no_api_2.export_template_job_enabled = False

        self.assertEqual(record._get_enabled_integrations(), self.integration_no_api_1)

        # 2.3
        self.integration_no_api_1.export_template_job_enabled = True
        self.integration_no_api_2.export_template_job_enabled = True

        self.assertEqual(record._get_enabled_integrations(), integrations)

        # 2.4
        record.company_id = self.integration_no_api_1.company_id

        self.assertEqual(record._get_enabled_integrations(), self.integration_no_api_1)

        # 2.5
        record.company_id = self.integration_no_api_2.company_id

        self.assertEqual(record._get_enabled_integrations(), self.integration_no_api_2)

    def test_is_need_export_images(self):
        integration = self.integration_no_api_1

        # 1. export_template_job_enabled = allow_export_images = True
        integration.allow_export_images = True

        self.assertTrue(
            integration._is_need_export_images({'image_1920': ''})
        )
        self.assertTrue(
            integration._is_need_export_images({'product_template_image_ids': ''})
        )
        self.assertTrue(
            integration._is_need_export_images({'product_variant_image_ids': ''})
        )

        self.assertFalse(
            integration._is_need_export_images({'image_variant_1920': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'name': ''})
        )

        # 2. export_template_job_enabled = False, allow_export_images = True
        integration.export_template_job_enabled = False

        self.assertFalse(
            integration._is_need_export_images({'image_1920': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_template_image_ids': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_variant_image_ids': ''})
        )

        # 3. export_template_job_enabled = True, allow_export_images = False
        integration.export_template_job_enabled = True
        integration.allow_export_images = False

        self.assertFalse(
            integration._is_need_export_images({'image_1920': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_template_image_ids': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_variant_image_ids': ''})
        )

        # 4. export_template_job_enabled = allow_export_images = False
        integration.export_template_job_enabled = False

        self.assertFalse(
            integration._is_need_export_images({'image_1920': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_template_image_ids': ''})
        )
        self.assertFalse(
            integration._is_need_export_images({'product_variant_image_ids': ''})
        )

    def test_is_need_export_product(self):
        integration = self.integration_no_api_1

        def _get_trackable_fields_patch(*args, **kw):
            return self.env['ir.model.fields']

        self.patch(type(integration), '_get_trackable_fields', _get_trackable_fields_patch)

        field = self.env.ref('product.field_product_template__name')

        integration.global_tracked_fields = [(4, field.id, 0)]

        # 1. export_template_job_enabled = True
        self.assertTrue(
            integration._is_need_export_product({field.name: ''})
        )

        # 2. export_template_job_enabled = False
        integration.export_template_job_enabled = False
        self.assertFalse(
            integration._is_need_export_product({field.name: ''})
        )

        # 3. global_tracked_fields = []
        integration.export_template_job_enabled = True
        integration.global_tracked_fields = [(6, 0, [])]

    def test_trigger_export_template_from_write(self):

        def with_delay_patch(*args, **kw):
            return args[0]

        def _is_need_export_images_patch(*args, **kw):
            return True

        def _is_need_export_product_patch(*args, **kw):
            return True

        def export_template_patch(*args, **kw):
            raise TestErrorExportTemplate('export_template_called')

        def export_images_job_patch(*args, **kw):
            raise TestErrorExportImage('export_images_job_called')

        integration = self.integration_no_api_1
        self.patch(type(integration), 'with_delay', with_delay_patch)
        self.patch(type(integration), '_is_need_export_images', _is_need_export_images_patch)
        self.patch(type(integration), '_is_need_export_product', _is_need_export_product_patch)
        self.patch(type(integration), 'export_template', export_template_patch)
        self.patch(type(integration), 'export_template_images_verbose', export_images_job_patch)

        # 1. Create template with one active integration
        vals = self.generate_product_data(
            name='product-1',
            integration=integration,
        )
        record = self.template.with_context(**self.skip_ctx).create(vals)

        # 1. Expected `export_template` method
        with self.assertRaises(TestErrorExportTemplate):
            record._trigger_export_single_template({})

        # 2. Expected `export_template_images_verbose` method
        def _is_need_export_product_patch2(*args, **kw):
            return False

        self.patch(type(integration), '_is_need_export_product', _is_need_export_product_patch2)

        with self.assertRaises(TestErrorExportImage):
            record._trigger_export_single_template({})

    def test_integration_company_mismatch_compute(self):
        integration1 = self.integration_no_api_1  # company A
        integration2 = self.integration_no_api_2  # company B
        self.assertNotEqual(integration1.company_id, integration2.company_id)

        tmpl = self.template.with_context(**self.skip_ctx).create(
            self.generate_product_data(name='p', integration=integration1)
        )

        # A
        tmpl.company_id = integration1.company_id
        tmpl.integration_ids = [(6, 0, integration1.ids)]
        tmpl._compute_integration_company_mismatch()
        self.assertFalse(tmpl.integration_company_mismatch)

        # B
        tmpl.integration_ids = [(6, 0, integration2.ids)]
        tmpl._compute_integration_company_mismatch()
        self.assertTrue(tmpl.integration_company_mismatch)

        # C
        tmpl.company_id = False
        tmpl.integration_ids = [(6, 0, (integration1 | integration2).ids)]
        tmpl._compute_integration_company_mismatch()
        self.assertFalse(tmpl.integration_company_mismatch)
