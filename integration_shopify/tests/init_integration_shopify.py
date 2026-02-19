# See LICENSE file for full copyright and licensing details.

from odoo.addons.integration.tests.config.integration_init import OdooIntegrationBase, load_xml

from .patch import ShopifyAPIClientPatchTest


class IntegrationShopifyBase(OdooIntegrationBase):

    def setUp(self):
        super(IntegrationShopifyBase, self).setUp()

        # Activate PL currency
        self.env.ref('base.PLN').active = True

        # Install PL language
        self.env['base.language.install'].create({
            'lang_ids': [(6, 0, [self.env.ref('base.lang_pl').id])]
        }).lang_install()

        # Load data
        load_xml(
            self.env,
            module='integration_shopify',
            path_file='tests/data/',
            filename='init_sale_integration_shopify.xml',
        )

        # Apply PL company to existing user
        self.company = self.env.ref('integration_shopify.test_integration_company_shopify_pl')
        self.integration_user.company_ids = [(4, self.company.id)]

        # Patch adapter
        self.integration = self.env.ref('integration_shopify.integration_shopify_test_1')
        self.patch(type(self.integration), 'get_class', self._get_class_patch)

        # Update WH data
        self.wh = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        location_line_ids = self.integration.location_line_ids.create({
            'integration_id': self.integration.id,
            'erp_location_id': self.wh.lot_stock_id.id,
            'external_location_id': self.env.ref('integration_shopify.integration_shopify_stock_location_external').id,
        })
        self.integration.location_line_ids = [(6, 0, location_line_ids.ids)]
        self.invoice_journal = self.env.ref('integration_shopify.integration_shopify_account_sales_journal_test')

        # Import payment methods
        self.integration.integrationApiImportPaymentMethods()

        # Import order statuses
        self.integration.integrationApiImportSaleOrderStatuses()

        # Import attributes
        external_records = self.integration.integrationApiImportAttributes()
        self.integration.integrationApiImportAttributeValues()
        external_records.run_import_attributes()

        # Import categories
        external_records = self.integration.integrationApiImportCategories()
        external_records.import_categories()

        # Import features
        self.integration.integrationApiImportFeatureValues()
        external_records = self.integration.integrationApiImportFeatures()
        external_records.run_import_features()

        # Accounts adjustments
        self.product1 = self.env.ref('integration_shopify.shopify_product_product_49620724449000')
        t = self.product1.product_tmpl_id.with_company(self.company)
        t.property_account_income_id = self.env.ref('integration_shopify.integration_shopify_account_a_income')
        t.property_account_expense_id = self.env.ref('integration_shopify.integration_shopify_account_a_expense')

        self.product2 = self.env.ref('integration_shopify.shopify_product_product_47738503495000')
        t = self.product2.product_tmpl_id.with_company(self.company)
        t.property_account_income_id = self.env.ref('integration_shopify.integration_shopify_account_a_income')
        t.property_account_expense_id = self.env.ref('integration_shopify.integration_shopify_account_a_expense')

    @property
    def adapter(self):
        return self.integration.adapter

    def _get_class_patch(self):
        return ShopifyAPIClientPatchTest

    def _set_permissions(self, orm_record):
        orm_record = orm_record.with_user(self.integration_user.id).with_company(self.company)
        return orm_record.with_context(company_id=self.company.id, **self._ctx)
