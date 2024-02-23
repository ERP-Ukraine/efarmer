# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import MagicMock, patch

from ...integration.models.fields import SendFields
from ...integration.models.fields.send_fields_product_product import \
    ProductProductSendMixin
from ...integration.models.fields.send_fields_product_template import \
    ProductTemplateSendMixin
from ...integration.models.product_product import ProductProduct
from .config.intuit_case import OdooIntegrationInit


class SendFieldsProductTemplateTest(SendFields, ProductTemplateSendMixin):
    pass


class SendFieldsProductProductTest(SendFields, ProductProductSendMixin):
    pass


class TestSendFieldsProductTemplate(OdooIntegrationInit):

    def setUp(self):
        super(TestSendFieldsProductTemplate, self).setUp()

        self.instance_pt_1 = self.create_instance(
            SendFieldsProductTemplateTest,
            self.product_pt_1,
        )
        self.instance_pt_pp_1 = self.create_instance(
            SendFieldsProductProductTest,
            self.product_pt_1.product_variant_id,
        )
        self.instance_pt_2 = self.create_instance(
            SendFieldsProductTemplateTest,
            self.product_pt_2,
        )

        self.pricelist_1 = self.env.ref('integration.pricelist_1')

    def create_instance(self, cls, product_obj):
        return cls(
            self.integration_no_api_1,
            product_obj,
        )

    def create_pricelist_item(self, product_obj):
        return self.env['product.pricelist.item'].create(
            {
                'pricelist_id': self.pricelist_1.id,
                'product_tmpl_id': product_obj.id,
                'product_id': False,
                'min_quantity': 5,
                'compute_price': 'fixed',
                'percent_price': 10.0,
                'applied_on': '1_product',
            }
        )

    # integration/models/fields/send_fields_product_template.py
    @patch.object(ProductProduct, 'init_variant_export_converter')
    def test_variant_converter(self, mock_init_variant_export_converter):
        """
        Test the 'variant_converter' method.

        This test verifies the behavior of the 'variant_converter' method in different scenarios:
        1. When 'mock_init_variant_export_converter' is assigned a return value.
        2. When '_sub_converter' is None, it should return the value set in
           'mock_init_variant_export_converter'.
        3. When '_sub_converter' is already set, it should return the existing value.
        """
        # Assighning return value to mock_init_variant_export_converter
        mock_init_variant_export_converter.return_value = "converter_by_product_variant_id"

        # Checking if _sub_converter is None
        result_1 = self.instance_pt_1.variant_converter()
        self.assertEqual(result_1, "converter_by_product_variant_id")

        # Checking if _sub_converter is existing
        self.instance_pt_1._sub_converter = "existing_converter"
        result_2 = self.instance_pt_1.variant_converter()
        self.assertEqual(result_2, "existing_converter")

    # integration/models/fields/send_fields_product_template.py
    def test_ensure_template_mapped(self):
        """
        Test the 'ensure_template_mapped' method.

        This test suite covers various scenarios of ensuring that the mapping of a product template
        and its variants to an external system works correctly:
        1. When 'ensure_mapped' method returns True, 'variant_converter' method returns a converter,
           and all variants are mapped.
        2. When 'ensure_mapped' method returns False.
        3. When the product template is mapped, but one of the variants is not mapped.
        """
        # Mocking 'ensure_mapped' method to return True
        self.instance_pt_1.ensure_mapped = MagicMock(return_value=True)

        # Mocking 'variant_converter' method
        self.instance_pt_1.variant_converter = MagicMock(return_value=self.instance_pt_pp_1)

        # Mocking 'get_variants' method
        self.instance_pt_1.get_variants = MagicMock(
            return_value=self.instance_pt_1.odoo_obj.product_variant_ids
        )

        # Checking that 'ensure_template_mapped' returns True when everything is mapped
        result = self.instance_pt_1.ensure_template_mapped()
        self.assertTrue(result)

        # Checking that 'ensure_template_mapped' returns False when 'ensure_mapped' returns False
        self.instance_pt_1.ensure_mapped.return_value = False
        result = self.instance_pt_1.ensure_template_mapped()
        self.assertFalse(result)

        # Checking that product template is not mapped, but variants are not mapped
        self.instance_pt_1.ensure_mapped.return_value = True

        self.product_pt_1_var_mapping.unlink()

        result = self.instance_pt_1.ensure_template_mapped()
        self.assertFalse(result)

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_false_no_variants(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to False
        - variant_ids do not exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants,
          and variant_converter are mocked to simulate the respective behavior.
        """
        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=[])
        self.instance_pt_1.get_variants = MagicMock(return_value=[])
        self.instance_pt_1.variant_converter = MagicMock(return_value=False)

        # Checking if force_sync_pricelist is False and variant_ids is not exist
        result = self.instance_pt_1.convert_pricelists()
        self.assertEqual(result, tuple())

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_false_with_variants(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to False
        - variant_ids exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants,
          and variant_converter are mocked to simulate the respective behavior.
        """
        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=[])
        self.instance_pt_1.get_variants = MagicMock(return_value=self.instance_pt_pp_1.odoo_obj)
        self.instance_pt_1.variant_converter = MagicMock(return_value=self.instance_pt_pp_1)

        # Checking if force_sync_pricelist is False and variant_ids is exist
        result = self.instance_pt_1.convert_pricelists()
        self.assertEqual(result, tuple())

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_true_no_variants(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to True
        - variant_ids do not exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants,
          and variant_converter are mocked to simulate the respective behavior.

        It verifies that the convert_pricelists method returns the expected tuple when
        force_sync_pricelist is True and there are no product variants.
        """
        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods and attributes
        self.instance_pt_1.odoo_obj.to_force_sync_pricelist = True
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=[])
        self.instance_pt_1.get_variants = MagicMock(return_value=[])
        self.instance_pt_1.variant_converter = MagicMock(return_value=False)

        # Checking if force_sync_pricelist is True and variant_ids is not exist
        result = self.instance_pt_1.convert_pricelists()
        expecterd_tmpl_data = (
            self.instance_pt_1.odoo_obj.id,
            self.instance_pt_1.odoo_obj._name,
            self.instance_pt_1.external_id,
            [],
            True,
        )
        expecterd_variant_data = []
        self.assertEqual(result, (expecterd_tmpl_data, expecterd_variant_data))

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_true_with_variants(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to True
        - variant_ids exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants, and
        variant_converter are mocked to simulate the respective behavior.

        It verifies that the convert_pricelists method returns the expected tuple when
        force_sync_pricelist is True and there are product variants.
        """
        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods and attributes
        self.instance_pt_1.odoo_obj.to_force_sync_pricelist = True
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=[])
        self.instance_pt_1.get_variants = MagicMock(return_value=self.instance_pt_pp_1.odoo_obj)
        self.instance_pt_1.variant_converter = MagicMock(return_value=self.instance_pt_pp_1)

        # Checking if force_sync_pricelist is True and variant_ids is exist
        result = self.instance_pt_1.convert_pricelists()
        expecterd_tmpl_data = (
            self.instance_pt_1.odoo_obj.id,
            self.instance_pt_1.odoo_obj._name,
            self.instance_pt_1.external_id,
            [],
            True,
        )
        expecterd_variant_data = [
            (
                self.instance_pt_pp_1.odoo_obj.id,
                self.instance_pt_pp_1.odoo_obj._name,
                self.instance_pt_pp_1.external_id,
                [],
                True,
            )
        ]
        self.assertEqual(result, (expecterd_tmpl_data, expecterd_variant_data))

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_true_with_variants_with_pricelist_ids(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to True
        - variant_ids exist
        - Pricelist items (product_pricelist_item) exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants, and
          variant_converter are mocked to simulate the respective behavior.

        It verifies that the convert_pricelists method returns the expected tuple when
        force_sync_pricelist is True, there are product variants, and pricelist items are available
        """
        # Creating pricelist item
        product_pricelist_item = self.create_pricelist_item(self.product_pt_1)

        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods and attributes
        self.instance_pt_1.odoo_obj.to_force_sync_pricelist = True
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=product_pricelist_item)
        self.instance_pt_1.get_variants = MagicMock(return_value=self.instance_pt_pp_1.odoo_obj)
        self.instance_pt_1.variant_converter = MagicMock(return_value=self.instance_pt_pp_1)

        self.instance_pt_pp_1._collect_specific_prices = MagicMock(return_value=[])

        # Checking if force_sync_pricelist is True and variant_ids is exist and pricelist is exist
        result = self.instance_pt_1.convert_pricelists()
        expecterd_tmpl_data = (
            self.instance_pt_1.odoo_obj.id,
            self.instance_pt_1.odoo_obj._name,
            self.instance_pt_1.external_id,
            product_pricelist_item,
            True,
        )
        expecterd_variant_data = [
            (
                self.instance_pt_pp_1.odoo_obj.id,
                self.instance_pt_pp_1.odoo_obj._name,
                self.instance_pt_pp_1.external_id,
                [],
                True,
            )
        ]
        self.assertEqual(result, (expecterd_tmpl_data, expecterd_variant_data))

    # integration/models/fields/send_fields_product_template.py
    def test_force_sync_pricelist_false_with_variants_with_pricelist_ids(self):
        """
        Test the 'convert_pricelists' method.

        Testing the convert_pricelists method under the following conditions:
        - force_sync_pricelist is set to False
        - variant_ids exist
        - Pricelist items (product_pricelist_item) exist
        - The methods ensure_external_code, _collect_specific_prices, get_variants, and
          variant_converter are mocked to simulate the respective behavior.

        It verifies that the convert_pricelists method returns the expected tuple when
        force_sync_pricelist is False, there are product variants, and pricelist items
        are available.
        """
        # Creating pricelist item
        product_pricelist_item = self.create_pricelist_item(self.product_pt_1)

        # Mock ensure_external_code method
        self.instance_pt_pp_1.ensure_external_code = MagicMock(return_value=True)

        # Mocking methods and attributes
        self.instance_pt_1._collect_specific_prices = MagicMock(return_value=product_pricelist_item)
        self.instance_pt_1.get_variants = MagicMock(return_value=self.instance_pt_pp_1.odoo_obj)
        self.instance_pt_1.variant_converter = MagicMock(return_value=self.instance_pt_pp_1)

        self.instance_pt_pp_1._collect_specific_prices = MagicMock(return_value=[])

        # Checking if force_sync_pricelist is True and variant_ids is exist and pricelist is exist
        result = self.instance_pt_1.convert_pricelists()
        expecterd_tmpl_data = (
            self.instance_pt_1.odoo_obj.id,
            self.instance_pt_1.odoo_obj._name,
            self.instance_pt_1.external_id,
            product_pricelist_item,
            False,
        )
        expecterd_variant_data = []
        self.assertEqual(result, (expecterd_tmpl_data, expecterd_variant_data))

    # integration/models/fields/send_fields_product_template.py
    def test_get_variants(self):
        """
        Test the 'get_variants' method.

        This test evaluates the behavior of the 'get_variants' method under different scenarios:
        1. When the product has only one variant, it should return that variant.
        2. When attribute lines and values are set on the product template, it should still return
           the variants.
        3. When the sequence of attribute values is changed, it should return the variants sorted
           accordingly.
        """
        # Check if the product has only one variant
        result_1 = self.instance_pt_1.get_variants()
        self.assertEqual(result_1, self.product_pt_1.product_variant_ids)

        # Set attribute and attribute values on the template
        self.product_pt_1.write({
            'attribute_line_ids': [
                (0, 0, {
                    'attribute_id': self.product_attribute_color.id,
                    'value_ids': [(6, 0, (
                        self.product_attribute_value_white.id,
                        self.product_attribute_value_black.id,
                    ))],
                }),
            ]
        })

        result_2 = self.instance_pt_1.get_variants()
        self.assertEqual(
            result_2,
            self.product_pt_1.product_variant_ids,
        )

        # Change sequence of attribute values
        self.product_attribute_color[0].write({'sequence': 3})

        result_3 = self.instance_pt_1.get_variants()
        self.assertEqual(
            result_3,
            self.product_pt_1.product_variant_ids[::-1],
        )

    # integration/models/fields/send_fields_product_template.py
    def test_get_kits(self):
        """
        Test the '_get_kits' method.

        This test evaluates the behavior of the '_get_kits' method under different scenarios:
        1. When the product doesn't have a kit, it should return an empty list.
        2. When a Bill of Materials (BOM) is created for the product, it should return a
           list of kits.
        3. When the 'to_external_record' method returns a valid external record for components,
        it should return the correct kit data.
        4. When the 'to_external_record' method returns an invalid external record for components,
        it should not match the expected kit data.
        5. When the 'to_external_record' method returns False for components,
        it should return a list with component data and 'product_id' set to False.
        6. When the 'mrp' module is not installed, it should return an empty list.
        """
        # Checking if the mrp module is not installed
        self.integration_no_api_1.write({'is_installed_mrp': False})
        self.assertFalse(self.instance_pt_2._get_kits())

        # Update the is_installed_mrp field
        self.integration_no_api_1._compute_is_installed_mrp()

        # Exit if the mrp module is not installed
        if not self.integration_no_api_1.is_installed_mrp:
            return

        # Checking product without kit
        self.assertFalse(self.instance_pt_2._get_kits())

        # Creating bom
        self.env['mrp.bom'].create(
            {
                'product_tmpl_id': self.product_pt_2.id,
                'type': 'phantom',
                'company_id': self.integration_no_api_1.company_id.id,
                'bom_line_ids': [
                    (0, 0, {
                        'product_id': self.product_pp_1.id,
                        'product_qty': 1,
                    })
                ]
            }
        )

        # Checking if product has kit
        kit_data = [
            {'components': [
                {
                    'qty': 1.0,
                    'name': '[default_code_Variant_1] Test Product Variant_1',
                    'product_id': self.external_pp_1.code,
                    'external_reference': False
                }
            ]}
        ]

        with self.cr.savepoint(), patch.object(
            type(self.env['integration.mapping.mixin']), 'to_external_record'
        ) as mock_to_external_record:
            # Checking if method to_external_recorder returns a valid external_record
            mock_to_external_record.return_value = self.external_pp_1
            self.assertEqual(self.instance_pt_2._get_kits(), kit_data)

            # Checking if method to_external_recorder returns a invalid external_record
            mock_to_external_record.return_value = self.external_pp_2
            self.assertNotEqual(self.instance_pt_2._get_kits(), kit_data)

            # Checking if method to_external_recorder returns False
            mock_to_external_record.return_value = self.external_pp_2
            mock_to_external_record.return_value = self.env[self.external_pp_1._name]
            self.assertEqual(
                self.instance_pt_2._get_kits(),
                [
                    {'components': [
                        {
                            'qty': 1.0,
                            'name': '[default_code_Variant_1] Test Product Variant_1',
                            'product_id': False,
                            'external_reference': False
                        }
                    ]}
                ]
            )
