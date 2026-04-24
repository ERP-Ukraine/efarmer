# See LICENSE file for full copyright and licensing details.

from odoo.addons.integration.tests.config.integration_init import OdooIntegrationBase, load_xml

from .patch import ShopifyAPIClientPatchTest


class IntegrationShopifyBase(OdooIntegrationBase):

    @classmethod
    def setUpClass(cls):
        super(IntegrationShopifyBase, cls).setUpClass()

        # Activate PL currency
        cls.env.ref('base.PLN').active = True

        # Install PL language
        cls.env['base.language.install'].create({
            'lang_ids': [(6, 0, [cls.env.ref('base.lang_pl').id])]
        }).lang_install()

        # Load data
        load_xml(
            cls.env,
            module='integration_shopify',
            path_file='tests/data/',
            filename='init_sale_integration_shopify.xml',
        )

        # Apply PL company to existing user
        cls.company = cls.env.ref('integration_shopify.test_integration_company_shopify_pl')
        # Access integration_user via env.ref since it's set up in parent's setUp (instance method)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        integration_user = cls.env.ref('integration.integration_user')
        integration_user.company_ids = [(4, cls.company.id)]

        # Patch adapter
        cls.integration = cls.env.ref('integration_shopify.integration_shopify_test_1')
        cls.classPatch(type(cls.integration), 'get_class', cls._get_class_patch)

        # Update WH data
        cls.wh = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        location_line_ids = cls.integration.location_line_ids.create({
            'integration_id': cls.integration.id,
            'erp_location_id': cls.wh.lot_stock_id.id,
            'external_location_id': cls.env.ref('integration_shopify.integration_shopify_stock_location_external').id,
        })
        cls.integration.location_line_ids = [(6, 0, location_line_ids.ids)]
        cls.invoice_journal = cls.env.ref('integration_shopify.integration_shopify_account_sales_journal_test')

        # Import payment methods
        cls.integration.integrationApiImportPaymentMethods()

        # Import order statuses
        cls.integration.integrationApiImportSaleOrderStatuses()

        # Import attributes
        external_records = cls.integration.integrationApiImportAttributes()
        cls.integration.integrationApiImportAttributeValues()
        external_records.run_import_attributes()

        # Import categories
        external_records = cls.integration.integrationApiImportCategories()
        external_records.import_categories()

        # Accounts adjustments
        cls.product1 = cls.env.ref('integration_shopify.shopify_product_product_49620724449000')
        t = cls.product1.product_tmpl_id.with_company(cls.company)
        t.property_account_income_id = cls.env.ref('integration_shopify.integration_shopify_account_a_income')
        t.property_account_expense_id = cls.env.ref('integration_shopify.integration_shopify_account_a_expense')

        cls.product2 = cls.env.ref('integration_shopify.shopify_product_product_47738503495000')
        t = cls.product2.product_tmpl_id.with_company(cls.company)
        t.property_account_income_id = cls.env.ref('integration_shopify.integration_shopify_account_a_income')
        t.property_account_expense_id = cls.env.ref('integration_shopify.integration_shopify_account_a_expense')

    @property
    def adapter(self):
        return self.integration.adapter

    @classmethod
    def _get_class_patch(cls):
        return ShopifyAPIClientPatchTest

    def _set_permissions(self, orm_record):
        orm_record = orm_record.with_user(self.integration_user.id).with_company(self.company)
        return orm_record.with_context(company_id=self.company.id, **self._ctx)
