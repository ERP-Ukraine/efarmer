# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from ..tools import TemplateHub
from .config.integration_init import OdooIntegrationBase, load_xml


@tagged('post_install', '-at_install', 'test_catalog_validation_company')
class TestCatalogValidationCompany(OdooIntegrationBase):
    """The Odoo side of the catalog validation looks only at the store's company and shared products."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        cls.company_a = cls.env.ref('integration.test_integration_company_1')
        cls.company_b = cls.env.ref('integration.test_integration_company_2')
        cls.integration = cls.env.ref('integration.integration_no_api_1')

    def _create_product(self, name, default_code, company=False):
        return self.env['product.product'].create({
            'name': name,
            'default_code': default_code,
            'company_id': company.id if company else False,
        })

    def _odoo_errors(self, integration=None, **context):
        integration = (integration or self.integration).with_context(**context)
        results = integration._run_validation_checks(TemplateHub([]))
        return results['odoo_system']

    def test_other_company_products_are_not_reported(self):
        # The same SKU in two companies is valid: each company has its own catalog.
        self._create_product('Product A', 'SKU-1', self.company_a)
        self._create_product('Product B', 'SKU-1', self.company_b)
        product_b_no_sku = self._create_product('Product B without SKU', False, self.company_b)

        errors = self._odoo_errors()

        self.assertNotIn('SKU-1', errors.get('duplicated_references', {}).get('items', {}))
        missing = errors.get('missing_variant_references', {}).get('items', [])
        self.assertNotIn(str(product_b_no_sku.id), {rec.id for rec in missing})

    def test_duplicates_inside_the_store_company_are_reported(self):
        product_1 = self._create_product('Product 1', 'SKU-1', self.company_a)
        product_2 = self._create_product('Product 2', 'SKU-1', self.company_a)

        errors = self._odoo_errors()

        duplicates = errors['duplicated_references']['items']
        self.assertIn('SKU-1', duplicates)
        self.assertEqual(
            {str(product_1.id), str(product_2.id)},
            {rec.id for rec in duplicates['SKU-1']},
        )

    def test_shared_products_are_still_checked(self):
        shared_1 = self._create_product('Shared 1', 'SKU-SHARED')
        shared_2 = self._create_product('Shared 2', 'SKU-SHARED')
        company_product = self._create_product('Product A', 'SKU-SHARED', self.company_a)
        self._create_product('Product B', 'SKU-SHARED', self.company_b)

        errors = self._odoo_errors()

        duplicates = errors['duplicated_references']['items']
        self.assertIn('SKU-SHARED', duplicates)
        self.assertEqual(
            {str(shared_1.id), str(shared_2.id), str(company_product.id)},
            {rec.id for rec in duplicates['SKU-SHARED']},
        )

    def test_result_does_not_depend_on_company_switcher(self):
        product_1 = self._create_product('Product 1', 'SKU-1', self.company_a)
        product_2 = self._create_product('Product 2', 'SKU-1', self.company_a)
        self._create_product('Product B', 'SKU-1', self.company_b)
        expected_ids = {str(product_1.id), str(product_2.id)}

        for allowed_companies in (
            [self.company_a.id],
            [self.company_b.id],
            [self.company_a.id, self.company_b.id],
        ):
            with self.subTest(allowed_companies=allowed_companies):
                errors = self._odoo_errors(allowed_company_ids=allowed_companies)

                duplicates = errors['duplicated_references']['items']
                self.assertEqual(expected_ids, {rec.id for rec in duplicates['SKU-1']})

    def test_other_store_gets_its_own_company_catalog(self):
        self._create_product('Product A', 'SKU-1', self.company_a)
        product_b_1 = self._create_product('Product B1', 'SKU-1', self.company_b)
        product_b_2 = self._create_product('Product B2', 'SKU-1', self.company_b)
        integration_b = self.env.ref('integration.integration_no_api_2')

        errors = self._odoo_errors(integration=integration_b)

        duplicates = errors['duplicated_references']['items']
        self.assertEqual(
            {str(product_b_1.id), str(product_b_2.id)},
            {rec.id for rec in duplicates['SKU-1']},
        )
