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
