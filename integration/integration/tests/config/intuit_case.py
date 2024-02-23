# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
from pathlib import Path

from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase
from odoo.tools import convert_file


class OdooIntegrationInit(TransactionCase):

    def setUp(self):
        super(OdooIntegrationInit, self).setUp()

        # Loading Integration data from xml
        self._load_xml(
            module='integration',
            path_file='tests/data/',
            filename='init_sale_integration.xml',
        )

        self.integration_no_api_1 = self.env.ref('integration.integration_no_api_1')
        self.integration_no_api_2 = self.env.ref('integration.integration_no_api_2')

        self.company_id_1 = self.env.ref('integration.test_integration_company_1')
        self.company_id_2 = self.env.ref('integration.test_integration_company_2')

        self.integration_administrator = self.env.ref('integration.integration_administrator')
        self.integration_user = self.env.ref('integration.integration_user')

        # Creating product attributes and attribute values
        self.product_attribute_color = self.env.ref('integration.product_attribute_color')
        self.product_attribute_value_white = self.env.ref(
            'integration.product_attribute_value_white')
        self.product_attribute_value_black = self.env.ref(
            'integration.product_attribute_value_black')

        # Creating Tax
        self.tax_1 = self.env.ref('integration.tax_1')

        # Creating product future
        self.feature_id = self.env.ref('integration.feature_id')
        self.feature_value_id = self.env.ref('integration.feature_value_id')

        # Creating product category
        self.product_public_category = self.env.ref('integration.product_public_category')
        self.integration_product_public_category_external = self.env.ref(
            'integration.integration_product_public_category_external')
        self.integration_product_public_category_mapping = self.env.ref(
            'integration.integration_product_public_category_mapping')

        # Creating product ecommerce field
        self.product_ecommerce_field_1 = self.env.ref('integration.product_ecommerce_field_1')
        self.product_ecommerce_field_mapping_1 = self.env.ref(
            'integration.product_ecommerce_field_mapping_1')

        self.product_variant_ecommerce_field_1 = self.env.ref(
            'integration.product_variant_ecommerce_field_1')
        self.product_variant_ecommerce_field_mapping_1 = self.env.ref(
            'integration.product_variant_ecommerce_field_mapping_1')

        self.product_ecommerce_field_2 = self.env.ref('integration.product_ecommerce_field_2')
        self.product_ecommerce_field_mapping_2 = self.env.ref(
            'integration.product_ecommerce_field_mapping_2')

        self.product_ecommerce_field_available_for_order = self.env.ref(
            'integration.product_ecommerce_field_available_for_order')
        self.product_ecommerce_field_mapping_available_for_order = self.env.ref(
            'integration.product_ecommerce_field_mapping_available_for_order')

        self.product_ecommerce_field_template_weight = self.env.ref(
            'integration.product_ecommerce_field_template_weight')
        self.product_ecommerce_field_mapping_template_weight = self.env.ref(
            'integration.product_ecommerce_field_mapping_template_weight')

        self.product_ecommerce_field_default_category = self.env.ref(
            'integration.product_ecommerce_field_default_category')
        self.product_ecommerce_field_mapping_default_category = self.env.ref(
            'integration.product_ecommerce_field_mapping_default_category')

        self.product_ecommerce_field_collections = self.env.ref(
            'integration.product_ecommerce_field_collections')
        self.product_ecommerce_field_mapping_collections = self.env.ref(
            'integration.product_ecommerce_field_mapping_collections')

        self.product_ecommerce_field_description = self.env.ref(
            'integration.product_ecommerce_field_description')
        self.product_ecommerce_field_mapping_description = self.env.ref(
            'integration.product_ecommerce_field_mapping_description')

        # Creating Product Templates
        vals_product_pt_1 = self.generate_product_data(
            name=1,
            integration=self.integration_no_api_1,
        )
        self.product_pt_1 = self.env['product.template']\
            .with_user(self.integration_administrator)\
            .create(vals_product_pt_1)

        vals_product_pt_2 = self.generate_product_data(
            name=2,
            integration=self.integration_no_api_1,
        )
        self.product_pt_2 = self.env['product.template']\
            .with_user(self.integration_administrator)\
            .create(vals_product_pt_2)

        # Creating Product Variants
        vals_product_pp_1 = self.generate_product_data(
            name='Variant_1',
            integration=self.integration_no_api_1,
        )

        self.product_pp_1 = self.env['product.product']\
            .with_user(self.integration_administrator)\
            .create(vals_product_pp_1)

        vals_product_pp_2 = self.generate_product_data(
            name='Variant_2',
            integration=self.integration_no_api_1,
        )
        self.product_pp_2 = self.env['product.product']\
            .with_user(self.integration_administrator)\
            .create(vals_product_pp_2)

        # Creating external
        self.external_pt_1 = self._create_external(
            self.product_pt_1,
            self.integration_no_api_1,
            '1111',
        )
        self.external_pt_1_var = self._create_external(
            self.product_pt_1.product_variant_id,
            self.integration_no_api_1,
            '1111-2222',
        )

        self.external_pt_2 = self._create_external(
            self.product_pt_2,
            self.integration_no_api_1,
            '3333',
        )
        self.external_pt_2_var = self._create_external(
            self.product_pt_2.product_variant_id,
            self.integration_no_api_1,
            '3333-4444',
        )

        self.external_pp_1 = self._create_external(
            self.product_pp_1,
            self.integration_no_api_1,
            '5555',
        )
        self.external_pp_2 = self._create_external(
            self.product_pp_2,
            self.integration_no_api_1,
            '6666'
        )

        # Creating mapping
        self.product_pt_1_mapping = self._create_mapping(
            self.product_pt_1,
            self.external_pt_1,
            self.integration_no_api_1,
        )
        self.product_pt_1_var_mapping = self._create_mapping(
            self.product_pt_1.product_variant_id,
            self.external_pt_1_var,
            self.integration_no_api_1,
        )

        self.product_pt_2_mapping = self._create_mapping(
            self.product_pt_2,
            self.external_pt_2,
            self.integration_no_api_1,
        )
        self.product_pt_2_var_mapping = self._create_mapping(
            self.product_pt_2.product_variant_id,
            self.external_pt_2_var,
            self.integration_no_api_1,
        )

        self.product_pp_1_mapping = self._create_mapping(
            self.product_pp_1,
            self.external_pp_1,
            self.integration_no_api_1,
        )
        self.product_pp_1_mapping = self._create_mapping(
            self.product_pp_2,
            self.external_pp_2,
            self.integration_no_api_1,
        )

    def get_all_integrations(self):
        return self.integration_no_api_1 | self.integration_no_api_2

    def get_integration_identity_key(self, integration, product, export_images=True):
        return integration._job_kwargs_export_template(
            product, export_images).get('identity_key')

    def generate_product_data(self, *, name, image='can_of_cola.png', integration=False):
        return {
            'name': 'Test Product %s' % name,
            'detailed_type': 'product',
            'default_code': 'default_code_%s' % name,
            'barcode': 'barcode_%s' % name,
            'integration_ids': integration and [(6, 0, integration.ids)],
            'image_1920': self._get_test_image(image),
            'standard_price': 10,
            'list_price': 15,
            'taxes_id': [(6, 0, self.tax_1.ids)],
        }

    def get_queue_job(self, identity_key):
        return self.env['queue.job'].search([('identity_key', '=', identity_key)])

    def _get_test_image(self, name):
        image_path = Path(__file__).resolve().parent.parent / Path('images') / Path(name)
        return base64.b64encode(image_path.read_bytes())

    def _load_xml(self, module, path_file, filename):
        file_path = get_module_resource(module, path_file, filename)
        convert_file(
            self.env.cr, module, '{}{}'.format(path_file, filename),
            {}, 'init', False, 'test', file_path,
        )

    def _create_external(self, product, integration, code):
        model = 'integration.{}.external'.format(product._name)
        return self.env[model].create({
            'integration_id': integration.id,
            'code': code,
            'name': product.name,
        })

    def _create_mapping(self, product, external, integration):
        model = 'integration.{}.mapping'.format(product._name)
        vals = {
            'integration_id': integration.id,
        }
        if product._name == 'product.template':
            vals.update({
                'template_id': product.id,
                'external_template_id': external.id
            })
        else:
            vals.update({
                'product_id': product.id,
                'external_product_id': external.id
            })
        return self.env[model].create(vals)
