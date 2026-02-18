# See LICENSE file for full copyright and licensing details.

import math

from odoo.tests import tagged
from odoo.tools.float_utils import float_is_zero
from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_bom_calculation')
class TestProductBomCalculation(OdooIntegrationInit):

    def setUp(self):
        super().setUp()
        self._create_test_locations()
        self._create_test_products()
        self._setup_boms()
        self._setup_stock_quantities()

    def _create_test_locations(self):
        """Create test warehouse and locations"""
        self.warehouse = self.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TEST',
        })
        self.stock_location = self.warehouse.lot_stock_id
        self.stock_location_company2 = None  # Will be created for company2 tests

    def _create_test_products(self):
        """Create test products for BOM calculation scenarios"""
        # Main product (storable goods)
        self.main_product = self.env['product.product'].create({
            'name': 'Main Product',
            'default_code': 'MAIN',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })

        # Components (storable goods)
        self.component_a = self.env['product.product'].create({
            'name': 'Component A',
            'default_code': 'COMP_A',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })

        self.component_b = self.env['product.product'].create({
            'name': 'Component B',
            'default_code': 'COMP_B',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_kgm').id,
        })

        # Special component types
        self.service_component = self.env['product.product'].create({
            'name': 'Service Component',
            'default_code': 'SERV_COMP',
            'type': 'service',
        })

        # “Consumable”: goods excluding inventory
        self.consumable_component = self.env['product.product'].create({
            'name': 'Consumable Component',
            'default_code': 'CONS_COMP',
            'type': 'consu',
            'is_storable': False,
        })

        # Raw materials (storable goods)
        self.material_a = self.env['product.product'].create({
            'name': 'Material for Component A',
            'default_code': 'MATERIAL_A',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })

        self.material_b = self.env['product.product'].create({
            'name': 'Material for Component B',
            'default_code': 'MATERIAL_B',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_kgm').id,
        })

    def _setup_boms(self):
        """Configure BOM structures for testing"""
        # BOM for Component A (1 material_a -> 1 component_a)
        self.env['mrp.bom'].create({
            'product_tmpl_id': self.component_a.product_tmpl_id.id,
            'product_id': self.component_a.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.component_a.uom_id.id,  # <— IMPORTANT in Odoo 19
            'bom_line_ids': [
                (0, 0, {
                    'product_id': self.material_a.id,
                    'product_qty': 1.0,
                    'product_uom_id': self.material_a.uom_id.id,  # <— IMPORTANT in Odoo 19
                })
            ]
        })

        # BOM for Component B (1 material_b -> 1 component_b)
        self.env['mrp.bom'].create({
            'product_tmpl_id': self.component_b.product_tmpl_id.id,
            'product_id': self.component_b.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.component_b.uom_id.id,  # <— IMPORTANT in Odoo 19
            'bom_line_ids': [
                (0, 0, {
                    'product_id': self.material_b.id,
                    'product_qty': 1.0,
                    'product_uom_id': self.material_b.uom_id.id,  # <— IMPORTANT in Odoo 19
                })
            ]
        })

        # BOM for main product (requires 2*A and 0.5 kg of B)
        self.main_bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.main_product.product_tmpl_id.id,
            'product_id': self.main_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.main_product.uom_id.id,  # <— IMPORTANT in Odoo 19
            'bom_line_ids': [
                (0, 0, {
                    'product_id': self.component_a.id,
                    'product_qty': 2.0,
                    'product_uom_id': self.component_a.uom_id.id,  # <— IMPORTANT in Odoo 19
                }),
                (0, 0, {
                    'product_id': self.component_b.id,
                    'product_qty': 0.5,
                    'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                }),
                (0, 0, {
                    'product_id': self.service_component.id,
                    'product_qty': 1.0,
                }),
                (0, 0, {
                    'product_id': self.consumable_component.id,
                    'product_qty': 1.0,
                })
            ]
        })

    def _set_onhand(self, product, location, qty, company=None):
        """
        Set on-hand quantity for a product at a given location/company
        using low-level quant APIs. Safe for tests and multi-company.

        :param product: recordset product.product (single)
        :param location: recordset stock.location (single)
        :param qty: float target on-hand
        :param company: res.company or None (defaults to env.company)
        """
        company = company or self.env.company

        # Build an env that guarantees correct company/visibility
        env = self.env(context=dict(
            self.env.context,
            company_id=company.id,
            allowed_company_ids=[company.id],
            compute_child=False,  # be explicit: use exactly this location
        ))
        Quant = env['stock.quant'].sudo()

        # Read current qty at this exact location (no children)
        current_qty = Quant._get_available_quantity(product, location)
        # Compare with UoM rounding precision to avoid float jitter
        if float_is_zero(current_qty - qty, precision_rounding=product.uom_id.rounding):
            return

        delta = qty - current_qty
        # Update (creates/moves lot-less quant rows under the hood)
        Quant._update_available_quantity(product, location, delta)

        # Ensure computed fields and caches are refreshed for subsequent reads
        env.flush_all()
        env.invalidate_all()

    def _setup_stock_quantities(self):
        """Configure test stock quantities using safe methods"""
        # Material A: 10 units (→ 10 * component_a)
        self._set_onhand(self.material_a, self.stock_location, 10.0)
        # Material B: 20 kg (→ 20 * component_b)
        self._set_onhand(self.material_b, self.stock_location, 20.0)

    def _compute_producible_qty(self, product, qty_field='qty_available', location=None):
        """Helper method to call _compute_qty_producible with context"""
        context = {}
        if location:
            context.update({
                'location': location.id,
                'compute_child': False,
            })
        return product.with_context(context)._compute_qty_producible(qty_field)

    # ---- TESTS ----

    def test_no_bom_returns_available_quantity(self):
        no_bom_product = self.env['product.product'].create({
            'name': 'No BOM Product',
            'default_code': 'NO_BOM_PROD',
            'type': 'consu',
            'is_storable': True,
        })
        self._set_onhand(no_bom_product, self.stock_location, 15.0)

        self.assertEqual(
            self._compute_producible_qty(no_bom_product),
            15.0,
            "Should return available quantity when no BOM exists",
        )

    def test_simple_bom_calculates_correctly(self):
        simple_product = self.env['product.product'].create({
            'name': 'Simple Product',
            'default_code': 'SIMP_PROD',
            'type': 'consu',
            'is_storable': True,
        })
        component = self.env['product.product'].create({
            'name': 'Simple Component',
            'default_code': 'SIMP_COMP',
            'type': 'consu',
            'is_storable': True,
        })

        self.env['mrp.bom'].create({
            'product_tmpl_id': simple_product.product_tmpl_id.id,
            'product_id': simple_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 2.0})]
        })

        self._set_onhand(component, self.stock_location, 10.0)

        self.assertEqual(
            self._compute_producible_qty(simple_product),
            5.0,
            "Should calculate producible quantity as component_qty / required_qty",
        )

    def test_missing_component_returns_zero(self):
        self._set_onhand(self.material_a, self.stock_location, 0.0)

        self.assertEqual(
            self._compute_producible_qty(self.main_product),
            0.0,
            "Should return 0 when a critical component is missing",
        )

    def test_recursive_bom_calculates_correctly(self):
        self.assertEqual(
            self._compute_producible_qty(self.component_a),
            10.0,
            "Should correctly calculate producible quantity for component with BOM",
        )
        self.assertEqual(
            self._compute_producible_qty(self.main_product),
            5.0,
            "Should correctly calculate producible quantity with recursive BOM",
        )

    def test_uom_conversion_in_bom(self):
        kg_component = self.env['product.product'].create({
            'name': 'KG Component',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_kgm').id,
        })

        gram_product = self.env['product.product'].create({
            'name': 'Gram Product',
            'default_code': 'GRAM_PROD',
            'type': 'consu',
            'is_storable': True,
        })

        self.env['mrp.bom'].create({
            'product_tmpl_id': gram_product.product_tmpl_id.id,
            'product_id': gram_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [
                (0, 0, {
                    'product_id': kg_component.id,
                    'product_qty': 500.0,
                    'product_uom_id': self.env.ref('uom.product_uom_gram').id,
                })
            ]
        })

        self._set_onhand(kg_component, self.stock_location, 2.0)  # 2 kg = 2000 g

        self.assertEqual(
            self._compute_producible_qty(gram_product),
            4.0,
            "Should correctly handle UOM conversion in BOM calculations",
        )

    def test_services_and_consumables_skipped(self):
        # The main product is limited to Component A (10 / 2 = 5)
        self.assertEqual(
            self._compute_producible_qty(self.main_product),
            5.0,
            "Service and consumable components should be skipped in calculation",
        )

        # Zero stock for consumable does not change anything (it is skipped anyway)
        # (onhand for is_storable=False is not set)

        self.assertEqual(
            self._compute_producible_qty(self.main_product),
            5.0,
            "Consumable components with zero stock should still be skipped",
        )

    def test_integer_division_flooring(self):
        precision_product = self.env['product.product'].create({
            'name': 'Precision Product',
            'default_code': 'PREC_PROD',
            'type': 'consu',
            'is_storable': True,
        })
        component = self.env['product.product'].create({
            'name': 'Precision Component',
            'default_code': 'PREC_COMP',
            'type': 'consu',
            'is_storable': True,
        })

        self.env['mrp.bom'].create({
            'product_tmpl_id': precision_product.product_tmpl_id.id,
            'product_id': precision_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 3.0})]
        })

        self._set_onhand(component, self.stock_location, 10.0)  # 10 // 3 = 3.0

        producible_qty = self._compute_producible_qty(precision_product)
        self.assertEqual(
            producible_qty, 3.0,
            "With integer division, 10 // 3 must yield 3.0"
        )

    def test_multi_company_bom_selection(self):
        # Company 2 and its warehouse/location
        company2 = self.env['res.company'].create({'name': 'Company 2'})
        wh2 = self.env['stock.warehouse'].with_company(company2).create({
            'name': 'WH2',
            'code': 'W2',
            'company_id': company2.id,
        })
        stock_loc2 = wh2.lot_stock_id

        # Stock for Company 1 (default)
        self._set_onhand(self.material_a, self.stock_location, 10.0, company=self.env.company)
        self._set_onhand(self.material_b, self.stock_location, 20.0, company=self.env.company)

        # --- Stock for Company 2 (will be used by recursion) ---
        self._set_onhand(self.material_a, stock_loc2, 20.0, company=company2)
        self._set_onhand(self.material_b, stock_loc2, 20.0, company=company2)

        # --- BOMs for components under Company 2 ---
        # 1 material_a -> 1 component_a
        self.env['mrp.bom'].with_company(company2).create({
            'product_tmpl_id': self.component_a.product_tmpl_id.id,
            'product_id': self.component_a.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.component_a.uom_id.id,  # <— IMPORTANT in Odoo 19
            'company_id': company2.id,
            'bom_line_ids': [(0, 0, {
                'product_id': self.material_a.id,
                'product_qty': 1.0,
                'product_uom_id': self.material_a.uom_id.id,  # <— IMPORTANT in Odoo 19
            })],
        })
        # 1 material_b -> 1 component_b
        self.env['mrp.bom'].with_company(company2).create({
            'product_tmpl_id': self.component_b.product_tmpl_id.id,
            'product_id': self.component_b.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.component_b.uom_id.id,  # <— IMPORTANT in Odoo 19
            'company_id': company2.id,
            'bom_line_ids': [(0, 0, {
                'product_id': self.material_b.id,
                'product_qty': 1.0,
                'product_uom_id': self.material_b.uom_id.id,  # <— IMPORTANT in Odoo 19
            })],
        })

        # Top-level BOM for Main Product under Company 2
        self.env['mrp.bom'].with_company(company2).create({
            'product_tmpl_id': self.main_product.product_tmpl_id.id,
            'product_id': self.main_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'product_uom_id': self.main_product.uom_id.id,  # <— IMPORTANT in Odoo 19
            'company_id': company2.id,
            'bom_line_ids': [
                (0, 0, {'product_id': self.component_a.id, 'product_qty': 2.0}),
                (0, 0, {
                    'product_id': self.component_b.id,
                    'product_qty': 0.5,
                    'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                }),
            ],
        })

        # Checks
        # Company 1:  material_a=10, material_b=20 кг -> compA=10, compB=20 -> MAIN = min(10/2, 20/0.5)=5
        qty_company1 = self._compute_producible_qty(
            self.main_product.with_company(self.env.company),
            location=self.stock_location
        )
        self.assertEqual(qty_company1, 5.0, "Should use correct BOM and stock for company 1")

        # Company 2:  material_a=20, material_b=20 кг -> compA=20, compB=20 -> MAIN = min(20/2, 20/0.5)=10
        qty_company2 = self._compute_producible_qty(
            self.main_product.with_company(company2),
            location=stock_loc2
        )
        self.assertEqual(qty_company2, 10.0, "Should use correct BOM and stock for company 2")

    def test_location_specific_stock_calculation(self):
        """Only stock in the specified sibling location should be used."""
        parent_location = self.stock_location.location_id
        company = self.stock_location.company_id or self.env.company

        location_a = self.env['stock.location'].create({
            'name': 'Location A',
            'location_id': parent_location.id,
            'usage': 'internal',
            'company_id': company.id,
        })
        location_b = self.env['stock.location'].create({
            'name': 'Location B',
            'location_id': parent_location.id,
            'usage': 'internal',
            'company_id': company.id,
        })

        # Set stock for material_a (as before)
        self._set_onhand(self.material_a, location_a, 10.0, company=company)
        self._set_onhand(self.material_a, location_b, 20.0, company=company)

        # Add stock for material_b in each location (fix: was missing)
        self._set_onhand(self.material_b, location_a, 10.0, company=company)  # Enough for 5 main (10 kg component_b)
        self._set_onhand(self.material_b, location_b, 20.0, company=company)  # Enough for 10 main (20 kg component_b)

        self.assertEqual(
            self._compute_producible_qty(self.main_product, location=location_a),
            5.0,
            "Should calculate based ONLY on stock in specified location",
        )
        self.assertEqual(
            self._compute_producible_qty(self.main_product, location=location_b),
            10.0,
            "Should calculate based ONLY on stock in specified location",
        )

    def test_bom_with_zero_quantity_component_returns_finite_value(self):
        """
        Test that a BOM with a component requiring zero quantity does not result in infinite producible quantity.
        It should not block production and should not cause infinite values.
        """
        # Create product with BOM containing a zero-quantity component
        zero_qty_product = self.env['product.product'].create({
            'name': 'Product with Zero Qty Component',
            'default_code': 'ZERO_QTY_PROD',
            'type': 'consu',
            'is_storable': True,
        })

        component = self.env['product.product'].create({
            'name': 'Regular Component',
            'default_code': 'REG_COMP',
            'type': 'consu',
            'is_storable': True,
        })

        zero_qty_component = self.env['product.product'].create({
            'name': 'Zero Quantity Component',
            'default_code': 'ZERO_COMP',
            'type': 'consu',
            'is_storable': True,
        })

        # BOM: requires 1 regular component and 0 of zero_qty_component
        self.env['mrp.bom'].create({
            'product_tmpl_id': zero_qty_product.product_tmpl_id.id,
            'product_id': zero_qty_product.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [
                (0, 0, {
                    'product_id': component.id,
                    'product_qty': 1.0,
                }),
                (0, 0, {
                    'product_id': zero_qty_component.id,
                    'product_qty': 0.0,
                }),
            ]
        })

        # Set stock
        self._set_onhand(component, self.stock_location, 5.0, company=self.env.company)
        self._set_onhand(zero_qty_component, self.stock_location, 100.0, company=self.env.company)

        # Compute producible quantity
        producible_qty = self._compute_producible_qty(zero_qty_product)

        # Assert finite value
        self.assertFalse(math.isinf(producible_qty), "Producible quantity should not be infinite")
        self.assertFalse(math.isnan(producible_qty), "Producible quantity should not be NaN")
        self.assertEqual(producible_qty, 5.0, "Should be limited by regular component")

        # Now remove stock from constraining component
        self._set_onhand(component, self.stock_location, 0.0, company=self.env.company)

        producible_qty_no_stock = self._compute_producible_qty(zero_qty_product)

        self.assertEqual(
            producible_qty_no_stock, 0.0,
            "When required component has zero stock, producible quantity should be 0"
        )

    def test_component_onhand_plus_producible_are_summed(self):
        """Component with its own BOM: on-hand + producible must be summed."""
        kit = self.env['product.product'].create({
            'name': 'Kit',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        raw = self.env['product.product'].create({
            'name': 'Raw',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        # 1 Raw -> 1 Kit
        self.env['mrp.bom'].create({
            'product_tmpl_id': kit.product_tmpl_id.id,
            'product_id': kit.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': raw.id, 'product_qty': 1.0})],
        })
        final = self.env['product.product'].create({
            'name': 'Final',
            'type': 'consu',
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        # Final needs 1 × Kit
        self.env['mrp.bom'].create({
            'product_tmpl_id': final.product_tmpl_id.id,
            'product_id': final.id,
            'type': 'normal',
            'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': kit.id, 'product_qty': 1.0})],
        })
        # On hand: Kit=5; Raw=50 => producible Kit=50
        self._set_onhand(kit, self.stock_location, 5.0)
        self._set_onhand(raw, self.stock_location, 50.0)
        qty = self._compute_producible_qty(final)
        self.assertEqual(qty, 55.0, "Final must consider 5 on-hand + 50 producible of Kit")
