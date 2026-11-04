# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_product_product_external')
class TestProductProductExternal(OdooIntegrationInit):

    def _prepare_external_variant(self, barcode):
        product = self.product_pt_1.product_variant_id
        product.with_context(skip_product_export=True).write({'barcode': barcode})

        external_variant = self.external_pt_1_var
        external_variant.write({
            'external_barcode': barcode,
            'external_product_template_id': self.external_pt_1.id,
        })

        return product, external_variant

    def test_filter_variants_by_barcode_validation_disabled(self):
        product, external_variant = self._prepare_external_variant('TEST_BARCODE')
        self.integration_no_api_1.validate_barcode = False

        variant = external_variant._filter_variants_by_barcode(product)

        self.assertFalse(variant)

    def _apply_stock(self, qty, **product_vals):
        product = self.product_pt_1.product_variant_id
        if product_vals:
            product.with_context(skip_product_export=True).write(product_vals)

        location = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id
        result = self.external_pt_1_var.apply_stock_levels(qty, location)
        available_qty = self.env['stock.quant']._get_available_quantity(product, location)

        return result, available_qty

    def test_apply_stock_levels_quantity_tracked_product(self):
        result, available_qty = self._apply_stock(7)

        self.assertEqual(available_qty, 7.0)
        self.assertIn('set to 7.0', result)
        self.assertIn(self.product_pt_1.product_variant_id.display_name, result)

    def test_apply_stock_levels_skips_lot_tracked_product(self):
        result, available_qty = self._apply_stock(7, tracking='lot')

        self.assertEqual(available_qty, 0.0)
        self.assertIn('Skipped', result)
        self.assertIn('lots or serial numbers', result)

    def test_apply_stock_levels_skips_untracked_inventory_product(self):
        result, available_qty = self._apply_stock(7, is_storable=False)

        self.assertEqual(available_qty, 0.0)
        self.assertIn('Skipped', result)
        self.assertIn('Track Inventory', result)

    def test_apply_stock_job_description_contains_product_name(self):
        location = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id

        job_kwargs = self.integration_no_api_1._job_kwargs_apply_stock_single('1111-2222', location, 'Test Product')

        self.assertIn('1111-2222 (Test Product)', job_kwargs['description'])
        self.assertIn(location.display_name, job_kwargs['description'])

    def test_apply_stock_job_description_without_product_name(self):
        location = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1).lot_stock_id

        job_kwargs = self.integration_no_api_1._job_kwargs_apply_stock_single('1111-2222', location)

        self.assertIn('Single Product: 1111-2222 →', job_kwargs['description'])
