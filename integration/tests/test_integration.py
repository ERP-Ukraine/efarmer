# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestIntegration(OdooIntegrationInit):

    def setUp(self):
        super(TestIntegration, self).setUp()

    def test_create_job_after_creating_product(self):
        # Create product as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Testing as Integration Administrator
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_as_admin = self.get_queue_job(identity_key_1)
        self.assertEqual(queue_job_as_admin.identity_key, identity_key_1)

        # Create product as Integration User
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )
        product_2 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_2)

        # Testing as Integration User
        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_as_user = self.get_queue_job(identity_key_2)
        self.assertEqual(queue_job_as_user.identity_key, identity_key_2)

    def test_allow_export_images(self):
        # Check allow_export_images is True for Integration
        self.assertTrue(self.integration_no_api_1.allow_export_images)

        # Create product_1 as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Testing as Integration Administrator(allow_export_images=True)
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_as_admin = self.get_queue_job(identity_key_1)
        self.assertTrue(queue_job_as_admin)

        # Create product_2 as Integration User
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )
        product_2 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_2)

        # Testing as Integration Administrator(allow_export_images=True)
        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_as_user = self.get_queue_job(identity_key_2)
        self.assertTrue(queue_job_as_user)

        # Disable allow_export_images for Integration
        self.integration_no_api_1.write({'allow_export_images': False})

        # Check allow_export_images is False for Integration
        self.assertFalse(self.integration_no_api_1.allow_export_images)

        # Create product_3 as Integration Administrator
        vals_product_3 = self.generate_product_data(
            name='job 3',
            integration=self.integration_no_api_1,
        )
        product_3 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_3)

        # Testing as Integration Administrator(allow_export_images=False)
        # _export_images = export_images and integration.allow_export_images
        identity_key_3 = self.get_integration_identity_key(
            self.integration_no_api_1,
            product_3,
            export_images=False,
        )
        queue_job_as_admin = self.get_queue_job(identity_key_3)
        self.assertTrue(queue_job_as_admin)

        # Create product_4 as Integration User
        vals_product_4 = self.generate_product_data(
            name='job 4',
            integration=self.integration_no_api_1,
        )
        product_4 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_4)

        # Testing as Integration User(allow_export_images=False)
        # _export_images = export_images and integration.allow_export_images
        identity_key_3 = self.get_integration_identity_key(
            self.integration_no_api_1,
            product_4,
            export_images=False,
        )
        queue_job_as_user = self.get_queue_job(identity_key_3)
        self.assertTrue(queue_job_as_user)

    def test_skip_product_export(self):
        # Create product_1 as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .with_context(skip_product_export=True) \
            .create(vals_product_1)

        # Testing as Integration Administrator
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_as_admin = self.get_queue_job(identity_key_1)
        self.assertFalse(queue_job_as_admin)

        # Create product as Integration User
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )
        product_2 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .with_context(skip_product_export=True) \
            .create(vals_product_2)

        # Testing as Integration User
        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_as_user = self.get_queue_job(identity_key_2)
        self.assertFalse(queue_job_as_user)

    def test_export_template_job_enabled(self):
        # Disable export_template_job_enabled for Integration
        self.integration_no_api_1.write({'export_template_job_enabled': False})

        # Check export_template_job_enabled is False for Integration
        self.assertFalse(self.integration_no_api_1.export_template_job_enabled)

        # Create product_1 as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Testing as Integration Administrator
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_as_admin = self.get_queue_job(identity_key_1)
        self.assertFalse(queue_job_as_admin)

        # Create product as Integration User
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )
        product_2 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_2)

        # Testing as Integration User
        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_as_user = self.get_queue_job(identity_key_2)
        self.assertFalse(queue_job_as_user)

    def test_apply_to_products(self):
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )

        # Disable apply_to_products for Integrations except self.integration_no_api_1
        for integration in self.integration_no_api_1.search(
            [('id', '!=', self.integration_no_api_1.id)]
        ):
            integration.write({'apply_to_products': False})

        # Check apply_to_products is not False for self.integration_no_api_1
        self.assertTrue(self.integration_no_api_1.apply_to_products)

        # Check apply_to_products is False for Integrations except self.integration_no_api_1
        for integration in self.integration_no_api_1.search(
            [('id', '!=', self.integration_no_api_1.id)]
        ):
            self.assertFalse(integration.apply_to_products)

        # Create product_1 as Integration Administrator without integrations
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Testing as Integration Administrator
        self.assertIn(self.integration_no_api_1, product_1.integration_ids)
        self.assertNotIn(self.integration_no_api_2, product_1.integration_ids)

        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )

        # Create product_2 as Integration User without integrations
        product_2 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_2)

        # Testing as Integration User
        self.assertIn(self.integration_no_api_1, product_2.integration_ids)
        self.assertNotIn(self.integration_no_api_2, product_2.integration_ids)

    def test_company_id(self):
        # Create product_1 as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Check product_1 has one integration
        self.assertEqual(len(product_1.integration_ids), 1)

        # Testing as Integration Administrator
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_as_admin = self.get_queue_job(identity_key_1)

        # Only one job was created because one integration was selected for product_1
        self.assertEqual(queue_job_as_admin.company_id, product_1.integration_ids.company_id)

        # Create product_2 as Integration Administrator
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.get_all_integrations(),
        )

        product_2 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_2)

        # Check product_2 has two integrations
        self.assertEqual(len(product_2.integration_ids), 2)

        # Testing as Integration Administrator, two jobs were created
        # because two integrations were selected for product_2
        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_as_admin_unt_1 = self.get_queue_job(identity_key_2)
        self.assertEqual(queue_job_as_admin_unt_1.identity_key, identity_key_2)

        identity_key_3 = self.get_integration_identity_key(self.integration_no_api_2, product_2)
        queue_job_as_admin_int_2 = self.get_queue_job(identity_key_3)
        self.assertEqual(queue_job_as_admin_int_2.identity_key, identity_key_3)

        # Create product_3 as Integration User
        vals_product_3 = self.generate_product_data(
            name='job 3',
            integration=self.integration_no_api_1,
        )
        product_3 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_3)

        # Check product_3 has one integration
        self.assertEqual(len(product_3.integration_ids), 1)

        # Testing as Integration User
        identity_key_4 = self.get_integration_identity_key(self.integration_no_api_1, product_3)
        queue_job_as_user = self.get_queue_job(identity_key_4)

        # Only one job was created because one integration was selected for product_3
        self.assertEqual(queue_job_as_user.company_id, product_3.integration_ids.company_id)

        # Create product_4 as Integration User
        vals_product_4 = self.generate_product_data(
            name='job 4',
            integration=self.get_all_integrations(),
        )

        product_4 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_4)

        # Check product_4 has two integrations
        self.assertEqual(len(product_4.integration_ids), 2)

        # Testing as Integration User, two jobs were created
        # because two integrations were selected for product_4
        identity_key_5 = self.get_integration_identity_key(self.integration_no_api_1, product_4)
        queue_job_as_user_unt_1 = self.get_queue_job(identity_key_5)
        self.assertEqual(queue_job_as_user_unt_1.identity_key, identity_key_5)

        identity_key_6 = self.get_integration_identity_key(self.integration_no_api_2, product_4)
        queue_job_as_user_int_2 = self.get_queue_job(identity_key_6)
        self.assertEqual(queue_job_as_user_int_2.identity_key, identity_key_6)

    def test_mandatory_fields_initial_product_export(self):
        # 1.1 Create product_1 as Integration Administrator
        vals_product_1 = self.generate_product_data(
            name='job 1',
            integration=self.integration_no_api_1,
        )
        vals_product_1.update({'default_code': False})
        product_1 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .create(vals_product_1)

        # Check default_code is False for product_1
        self.assertFalse(product_1.default_code)

        # Testing as Integration Administrator
        identity_key_1 = self.get_integration_identity_key(self.integration_no_api_1, product_1)
        queue_job_1 = self.get_queue_job(identity_key_1)
        # The job will be created and will fail (even if no default_code is specified)
        # to alert the user about issues
        self.assertTrue(queue_job_1)

        # 1.2 Testing as Integration Administrator(manual_trigger=True)
        vals_product_2 = self.generate_product_data(
            name='job 2',
            integration=self.integration_no_api_1,
        )
        vals_product_2.update({'default_code': False})
        product_2 = self.env['product.template'] \
            .with_user(self.integration_administrator) \
            .with_context(manual_trigger=True).create(vals_product_2)

        identity_key_2 = self.get_integration_identity_key(self.integration_no_api_1, product_2)
        queue_job_2 = self.get_queue_job(identity_key_2)
        # The job will be created and will fail (even if no default_code is specified)
        # to alert the user about issues
        self.assertTrue(queue_job_2)

        # 2.1 Create product_3 as Integration User
        vals_product_3 = self.generate_product_data(
            name='job 3',
            integration=self.integration_no_api_1,
        )
        vals_product_3.update({'default_code': False})
        product_3 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .create(vals_product_3)

        # Check default_code is False for product_3
        self.assertFalse(product_3.default_code)

        # Testing as Integration User
        identity_key_3 = self.get_integration_identity_key(self.integration_no_api_1, product_3)
        queue_job_3 = self.get_queue_job(identity_key_3)
        # The job will be created and will fail (even if no default_code is specified)
        # to alert the user about issues
        self.assertTrue(queue_job_3)

        # 2.2 Testing as Integration User(manual_trigger=True)
        vals_product_4 = self.generate_product_data(
            name='job 4',
            integration=self.integration_no_api_1,
        )
        vals_product_4.update({'default_code': False})
        product_4 = self.env['product.template'] \
            .with_user(self.integration_user) \
            .with_context(manual_trigger=True).create(vals_product_4)

        # Testing as Integration User
        identity_key_4 = self.get_integration_identity_key(self.integration_no_api_1, product_4)
        queue_job_4 = self.get_queue_job(identity_key_4)
        # The job will be created and will fail (even if no default_code is specified)
        # to alert the user about issues
        self.assertTrue(queue_job_4)
