# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase


@tagged('post_install', '-at_install')
class TestLocationMappingWarning(IntegrationShopifyBase):
    """The warning is raised only when one warehouse is mapped to different Shopify locations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Warehouse = cls.env['stock.warehouse'].with_company(cls.company)
        cls.wh_a = Warehouse.create({'name': 'warning-wh-a', 'code': 'WWA', 'company_id': cls.company.id})
        cls.wh_b = Warehouse.create({'name': 'warning-wh-b', 'code': 'WWB', 'company_id': cls.company.id})

        Location = cls.env['stock.location'].with_company(cls.company)
        cls.loc_a1 = cls.wh_a.lot_stock_id
        cls.loc_a2 = Location.create({'name': 'A2', 'usage': 'internal', 'location_id': cls.wh_a.view_location_id.id})
        cls.loc_b1 = cls.wh_b.lot_stock_id

        External = cls.env['integration.stock.location.external']
        cls.ext_1 = External.create({'code': 'ext-1', 'name': 'Shopify 1', 'integration_id': cls.integration.id})
        cls.ext_2 = External.create({'code': 'ext-2', 'name': 'Shopify 2', 'integration_id': cls.integration.id})

    def _map(self, *pairs):
        """Replace the location mapping of the store with the given (Odoo location, Shopify location) pairs."""
        self.integration.location_line_ids = [(5, 0, 0)] + [
            (0, 0, {
                'integration_id': self.integration.id,
                'erp_location_id': location.id,
                'external_location_id': external.id,
            })
            for location, external in pairs
        ]

    def test_different_shopify_locations_in_one_warehouse_warn(self):
        self._map((self.loc_a1, self.ext_1), (self.loc_a2, self.ext_2))

        self.assertTrue(self.integration.invalid_location_mapping)

    def test_locations_of_one_warehouse_in_one_shopify_location_do_not_warn(self):
        self._map((self.loc_a1, self.ext_1), (self.loc_a2, self.ext_1))

        self.assertFalse(self.integration.invalid_location_mapping)

    def test_different_warehouses_do_not_warn(self):
        self._map((self.loc_a1, self.ext_1), (self.loc_b1, self.ext_2))

        self.assertFalse(self.integration.invalid_location_mapping)

    def test_warning_follows_mapping_changes(self):
        self._map((self.loc_a1, self.ext_1), (self.loc_a2, self.ext_2))
        self.assertTrue(self.integration.invalid_location_mapping)

        self.integration.location_line_ids.filtered(
            lambda line: line.erp_location_id == self.loc_a2
        ).external_location_id = self.ext_1

        self.assertFalse(self.integration.invalid_location_mapping)
