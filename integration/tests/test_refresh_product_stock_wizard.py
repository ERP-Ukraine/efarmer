# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tools import mute_logger

from .config.integration_init import OdooIntegrationInit
from ..exceptions import ErrorStore as es


@tagged('post_install', '-at_install', 'test_refresh_product_stock_wizard')
class TestRefreshProductStockWizard(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestRefreshProductStockWizard, cls).setUpClass()

        cls._create_test_locations()

    def setUp(self):
        super().setUp()

        self.integration_no_api_1.location_line_ids.unlink()
        self.integration_no_api_2.location_line_ids.unlink()

    # -------------------------
    # Helpers
    # -------------------------

    @classmethod
    def _create_test_locations(cls):
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Refresh Stock Test Warehouse',
            'code': 'RST',
        })
        cls.stock_location = cls.warehouse.lot_stock_id

        cls.second_location = cls.env['stock.location'].create({
            'name': 'Second Refresh Stock Location',
            'usage': 'internal',
            'location_id': cls.stock_location.location_id.id,
        })

    def _create_product(self, name='Refresh Stock Product', integration=False):
        vals = self.generate_product_data(
            name=name,
            integration=integration or self.env['sale.integration'],
        )
        return self.env['product.template'] \
            .with_context(skip_product_export=True) \
            .create(vals)

    def _create_external_location(self, integration, name='Test External Location', code='TEST_LOC'):
        return self.env['integration.stock.location.external'].create({
            'integration_id': integration.id,
            'name': name,
            'code': code,
        })

    def _create_location_mapping(self, integration, location=None, external_location=None):
        location = location or self.stock_location
        external_location = external_location or self._create_external_location(integration)

        return self.env['external.stock.location.line'].create({
            'integration_id': integration.id,
            'erp_location_id': location.id,
            'external_location_id': external_location.id,
        })

    def _create_external_product(self, integration, product, code='TEST_PRODUCT_CODE'):
        external_product = self.env['integration.product.product.external'].create({
            'integration_id': integration.id,
            'code': code,
            'name': product.name,
            'external_reference': code,
        })
        external_product.create_or_update_mapping(odoo_id=product.id)
        return external_product

    def _create_wizard(self, product_template, integration=False):
        values = {
            'template_id': product_template.id,
        }
        if integration:
            values['integration_id'] = integration.id

        return self.env['refresh.product.stock.wizard'].create(values)

    # -------------------------
    # Tests
    # -------------------------

    @mute_logger('odoo.tools.translate')
    def test_refresh_stock_action_requires_connected_store(self):
        """Muted: `ErrorStore.raise_error`/`format_message` are (class/static)methods
        with no `self`, so Odoo's `_()` can't resolve a language on their frame and
        logs "no translation language detected" here - expected, not a bug.
        """
        product_template = self._create_product(integration=False)

        self.assertFalse(product_template.product_variant_ids.integration_ids)

        with self.assertRaises(es.UserError):
            product_template.action_run_refresh_stock_from_external()

    def test_refresh_stock_wizard_selects_default_integration(self):
        self._create_location_mapping(self.integration_no_api_1)

        product_template = self._create_product(
            name='Product with one store',
            integration=self.integration_no_api_1,
        )

        wizard = self._create_wizard(product_template)

        self.assertEqual(wizard.integration_id, self.integration_no_api_1)
        self.assertEqual(wizard.location_id, self.stock_location)

    def test_refresh_stock_wizard_requires_location_mapping(self):
        product_template = self._create_product(
            name='Product without location mapping',
            integration=self.integration_no_api_1,
        )

        wizard = self._create_wizard(
            product_template,
            integration=self.integration_no_api_1,
        )

        with self.assertRaises(es.UserError):
            wizard._get_refresh_location_pairs()

    def test_refresh_stock_wizard_blocks_duplicate_odoo_location_mapping(self):
        product_template = self._create_product(
            name='Product with duplicate Odoo mappings',
            integration=self.integration_no_api_1,
        )
        wizard = self._create_wizard(
            product_template,
            integration=self.integration_no_api_1,
        )

        external_location_1 = self._create_external_location(
            self.integration_no_api_1,
            name='External Location 1',
            code='EXT_1',
        )
        external_location_2 = self._create_external_location(
            self.integration_no_api_1,
            name='External Location 2',
            code='EXT_2',
        )

        lines = self.env['refresh.product.stock.wizard.line'].create([
            {
                'wizard_id': wizard.id,
                'erp_location_id': self.stock_location.id,
                'external_location_id': external_location_1.id,
            },
            {
                'wizard_id': wizard.id,
                'erp_location_id': self.stock_location.id,
                'external_location_id': external_location_2.id,
            },
        ])

        with self.assertRaises(es.UserError):
            wizard._check_one_to_one(lines)

    def test_refresh_stock_wizard_blocks_duplicate_external_location_mapping(self):
        product_template = self._create_product(
            name='Product with duplicate external mappings',
            integration=self.integration_no_api_1,
        )
        wizard = self._create_wizard(
            product_template,
            integration=self.integration_no_api_1,
        )

        external_location = self._create_external_location(
            self.integration_no_api_1,
            name='External Location',
            code='EXT_1',
        )

        lines = self.env['refresh.product.stock.wizard.line'].create([
            {
                'wizard_id': wizard.id,
                'erp_location_id': self.stock_location.id,
                'external_location_id': external_location.id,
            },
            {
                'wizard_id': wizard.id,
                'erp_location_id': self.second_location.id,
                'external_location_id': external_location.id,
            },
        ])

        with self.assertRaises(es.UserError):
            wizard._check_one_to_one(lines)

    def test_refresh_stock_wizard_uses_only_mapped_external_variant_records(self):
        self._create_location_mapping(self.integration_no_api_1)

        product_template = self._create_product(
            name='Product with external mapping',
            integration=self.integration_no_api_1,
        )
        product = product_template.product_variant_id

        external_product = self._create_external_product(
            self.integration_no_api_1,
            product,
            code='MAPPED_PRODUCT_CODE',
        )

        wizard = self._create_wizard(
            product_template,
            integration=self.integration_no_api_1,
        )

        external_variant_records, skipped_variant_count = wizard._get_refresh_variant_data()

        self.assertEqual(external_variant_records, external_product)
        self.assertEqual(skipped_variant_count, 0)
