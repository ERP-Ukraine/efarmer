# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_export_inventory')
class TestIntegrationExportInventory(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestIntegrationExportInventory, cls).setUpClass()

        cls._create_test_locations()
        cls._create_kit_and_components()

        cls._mappings_ready = False
        cls.external_product = False

    def setUp(self):
        super().setUp()

        if not self.__class__._mappings_ready:
            self._configure_external_location_mapping()
            self._configure_external_product_mapping()
            self.__class__._mappings_ready = True

        self.external_product = self.__class__.external_product

    # -------------------------
    # Helpers
    # -------------------------

    @classmethod
    def _create_test_locations(cls):
        """Create test warehouse and locations."""
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TEST',
        })
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.stock_location_company2 = None  # reserved for future tests

    @classmethod
    def _create_kit_and_components(cls):
        """Create KIT + components + phantom BOM + external mapping (once per class)."""
        # Components
        cls.component_1 = cls.env['product.product'].create({
            'name': 'Component 1',
            'type': 'consu',
            'is_storable': True,
        })
        cls.component_2 = cls.env['product.product'].create({
            'name': 'Component 2',
            'type': 'consu',
            'is_storable': True,
        })

        # KIT product
        cls.kit_product = cls.env['product.product'].create({
            'name': 'KIT Product',
            'type': 'consu',
            'is_storable': True,
            'default_code': 'KIT001',
        })

        # Phantom BOM (KIT)
        cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.kit_product.product_tmpl_id.id,
            'type': 'phantom',
            'product_qty': 1,
            'bom_line_ids': [
                (0, 0, {'product_id': cls.component_1.id, 'product_qty': 1}),
                (0, 0, {'product_id': cls.component_2.id, 'product_qty': 1}),
            ],
        })

    def _configure_external_location_mapping(self):
        """
        Configure inventory location for integration (required by _collect_inventory_data).
        """
        external_location = self.env['integration.stock.location.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'name': 'Test Location',
            'code': 'TEST_LOC',
        })

        self.env['external.stock.location.line'].create({
            'integration_id': self.integration_no_api_1.id,
            'erp_location_id': self.stock_location.id,
            'external_location_id': external_location.id,
        })

    def _configure_external_product_mapping(self):
        """Create external product record and mapping for kit product."""
        self.external_product = self.env['integration.product.product.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': f'EXT_{self.kit_product.id}',
            'name': self.kit_product.name,
            'external_reference': self.kit_product.default_code or str(self.kit_product.id),
        })
        self.external_product.create_or_update_mapping(odoo_id=self.kit_product.id)
        self.__class__.external_product = self.external_product

    # -------------------------
    # Utilities
    # -------------------------

    def _set_product_qty(self, product, qty, location=None):
        """Set available quantity for a product in a given location."""
        location = location or self.stock_location
        self.env['stock.quant']._update_available_quantity(product, location, qty)

    # -------------------------
    # Tests
    # -------------------------

    def test_prepare_inventory_data_kit_product(self):
        """KIT products must export stock based only on product quantity."""
        # Set stock for components
        self._set_product_qty(self.component_1, 10, self.stock_location)
        self._set_product_qty(self.component_2, 10, self.stock_location)

        # Sanity check: kit qty is derived from components
        qty_field = self.integration_no_api_1.synchronise_qty_field
        product_qty = getattr(
            self.kit_product.with_context(location=self.stock_location.id),
            qty_field,
        )
        self.assertEqual(product_qty, 10)

        # Collect inventory data
        inventory_data, _ = self.integration_no_api_1._collect_inventory_data(
            self.kit_product,
            raise_error=True,
        )

        exported_qty = inventory_data[self.external_product.code][0]['qty']
        self.assertEqual(exported_qty, 10)
