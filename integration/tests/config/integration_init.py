# See LICENSE file for full copyright and licensing details.

import base64
from pathlib import Path

from odoo.tests import TransactionCase
from odoo.tools import convert_file
from odoo.tools.misc import file_path


def load_xml(env, module, path_file, filename):
    pth = file_path(f'{module}/{path_file}/{filename}', ('xml',), env)
    convert_file(
        env, module, f'{path_file}/{filename}',
        idref={}, mode='init', pathname=pth,
    )


class OdooIntegrationBase(TransactionCase):

    def setUp(self):
        super(OdooIntegrationBase, self).setUp()

        self._ctx = {
            'queue_job__no_delay': 1,
        }

        # Loading Integration data from xml
        load_xml(
            self.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )

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
        account_receivable = self.env['account.account'].search([
            ('company_ids', 'in', self.company_id_1.id),
            ('account_type', '=', 'asset_current')
        ], limit=1)

        account_payable = self.env['account.account'].search([
            ('company_ids', 'in', self.company_id_1.id),
            ('account_type', '=', 'liability_payable')
        ], limit=1)

        tax_group_id = self.env['account.tax.group'].create({
            'name': 'Test tax group',
            'company_id': self.company_id_1.id,
            'tax_receivable_account_id': account_receivable.id,
            'tax_payable_account_id': account_payable.id,
        })
        self.tax_1 = self.env['account.tax'].create({
            'name': 'Test Tax 1',
            'amount': 10,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company_id_1.id,
            'tax_group_id': tax_group_id.id,
        })

        # Creating product category
        self.product_public_category = self.env.ref('integration.product_public_category')
        self.integration_product_public_category_external = self.env.ref(
            'integration.integration_product_public_category_external')
        self.integration_product_public_category_mapping = self.env.ref(
            'integration.integration_product_public_category_mapping')

    def generate_product_data(self, *, name, image='can_of_cola.png', integration=False):
        return {
            'name': 'Test Product %s' % name,
            'type': 'consu',
            'is_storable': True,
            'default_code': 'default_code_%s' % name,
            'barcode': 'barcode_%s' % name,
            'integration_ids': integration and [(6, 0, integration.ids)],
            'image_1920': self._get_test_image(image),
            'standard_price': 10,
            'list_price': 15,
            'taxes_id': [(6, 0, self.tax_1.ids)],
        }

    def _get_test_image(self, name):
        image_path = Path(__file__).resolve().parent.parent / Path('images') / Path(name)
        return base64.b64encode(image_path.read_bytes())


class OdooIntegrationInit(OdooIntegrationBase):

    def setUp(self):
        super(OdooIntegrationInit, self).setUp()

        # Create no-api integrations
        self.integration_no_api_1 = self.env.ref('integration.integration_no_api_1')
        self.integration_no_api_2 = self.env.ref('integration.integration_no_api_2')

        # Creating Product Templates
        vals_product_pt_1 = self.generate_product_data(
            name=1,
            integration=self.integration_no_api_1,
        )
        self.product_pt_1 = self.env['product.template'].with_context(skip_product_export=True) \
            .with_user(self.integration_administrator) \
            .create(vals_product_pt_1)

        vals_product_pt_2 = self.generate_product_data(
            name=2,
            integration=self.integration_no_api_1,
        )
        self.product_pt_2 = self.env['product.template'].with_context(skip_product_export=True) \
            .with_user(self.integration_administrator) \
            .create(vals_product_pt_2)

        # Creating Product Variants
        vals_product_pp_1 = self.generate_product_data(
            name='Variant_1',
            integration=self.integration_no_api_1,
        )

        self.product_pp_1 = self.env['product.product'].with_context(skip_product_export=True) \
            .with_user(self.integration_administrator) \
            .create(vals_product_pp_1)

        vals_product_pp_2 = self.generate_product_data(
            name='Variant_2',
            integration=self.integration_no_api_1,
        )
        self.product_pp_2 = self.env['product.product'].with_context(skip_product_export=True) \
            .with_user(self.integration_administrator) \
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
        return integration._job_kwargs_export_template(product, export_images).get('identity_key')

    def get_queue_job(self, identity_key):
        return self.env['queue.job'].search([('identity_key', '=', identity_key)])

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
