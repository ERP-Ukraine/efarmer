# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
from unittest.mock import MagicMock, patch

from ...integration.exceptions import ApiImportError
from ...integration.models.fields.receive_fields import ReceiveFields
from ...integration.models.integration_model_mixin import IntegrationModelMixin
from ...integration.models.sale_integration import SaleIntegration
from .config.intuit_case import OdooIntegrationInit
from .json_data import pt_pp_1


class TestReceiveFields(OdooIntegrationInit):

    def setUp(self):
        super(TestReceiveFields, self).setUp()

        self.ProductTemplate = self.env['product.template']
        self.ProductProduct = self.env['product.product']

    def create_instance(self, product_model, external_obj):
        return ReceiveFields(
            self.integration_no_api_1,
            product_model,
            external_obj,
        )

    # integration/models/fields/receive_fields.py
    def test_get_field_value(self):
        """
        testing method: get_field_value

        This test case covers the 'get_field_value' method under various scenarios:
        - Creating an instance and mocking relevant methods.
        - Testing if the 'get_field_value' method correctly retrieves field values.
        - Testing when the requested ecommerce field is not found.
        - Testing when the 'external_obj' is not available.

        It checks whether the 'get_field_value' method returns the expected field value
        based on the provided 'field_name' and the existence of the 'external_obj'
        and ecommerce field.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        instance._get_ecommerce_field = MagicMock(return_value=self.product_ecommerce_field_2)
        instance.calculate_field_value = MagicMock(return_value={'default_code': 'default_code_1'})
        instance._get_value = MagicMock(return_value=None)

        # test if external_obj and ecommerce field are exist
        result = instance.get_field_value('default_code')
        self.assertEqual(result, 'default_code_1')

        # test if ecommerce field is not exist
        instance._get_ecommerce_field = MagicMock(return_value=False)
        result = instance.get_field_value('default_code_1')
        self.assertIsNone(result)

        # test if external_obj is not exist
        instance.external_obj = False
        result = instance.get_field_value('default_code')
        self.assertIsNone(result)

    # integration/models/fields/receive_fields.py
    def test_convert_translated_field_to_odoo_format(self):
        """
        Test the 'convert_translated_field_to_odoo_format' method.

        This test case covers the 'convert_translated_field_to_odoo_format' method, which is
        responsible for converting translated field values to Odoo format.

        It tests the following scenarios:
        - When the input value is not a dictionary.
        - When the input value is a dictionary, but the language is not found in the dictionary.
        - When the input value is not None and contains language translations.
        - When the 'external_language_id' is not found in the 'language_codes' mapping.

        The method is expected to return the converted Odoo format for translated fields,
        considering the provided input and language mappings.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # test if value is not dict
        result_1 = instance.convert_translated_field_to_odoo_format([])
        self.assertEqual(result_1, [])

        # test if value is dict, but language is not in value
        result_2 = instance.convert_translated_field_to_odoo_format({'lang': 'wrong'})
        self.assertEqual(result_2, {'lang': 'wrong'})

        # test if value is not None
        value_1 = {'language': {'attrs': {'id': '1'}, 'value': 'Payment accepted'}}
        result_3 = instance.convert_translated_field_to_odoo_format(value_1)
        lang_id = self.env.ref('base.lang_en_GB').id
        self.assertEqual(
            result_3,
            {'language': {lang_id: 'Payment accepted'}},
        )

        # test if external_language_id is not in language_codes
        value_2 = {'language': {'attrs': {'id': '2'}, 'value': 'Payment accepted'}}
        result_4 = instance.convert_translated_field_to_odoo_format(value_2)
        self.assertEqual(result_4, {'language': {}})

    # integration/models/fields/receive_fields.py
    def test_get_simple_value(self):
        """
        testing method: _get_simple_value

        Test the '_get_simple_value' method.

        This test case covers the '_get_simple_value' method, which is responsible for
        retrieving simple field values from the external system and preparing them for
        import into Odoo.

        It mocks the '_get_value' and '_prepare_simple_value' methods and verifies that
        '_get_simple_value' correctly retrieves and prepares the simple field value.

        The expected result is a dictionary with the Odoo field name as the key and the prepared
        value as the value.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        instance._get_value = MagicMock(return_value="default_code")
        instance._prepare_simple_value = MagicMock(return_value="value_default_code")

        result = instance._get_simple_value(self.product_variant_ecommerce_field_1)
        self.assertEqual(result, {'default_code': 'value_default_code'})

    # integration/models/fields/receive_fields.py
    def test_prepare_simple_value(self):
        """
        Test the '_prepare_simple_value' method.

        This test case covers the '_prepare_simple_value' method, which is responsible for
        preparing simple field values retrieved from the external system for import into Odoo.

        It tests various scenarios based on field types and input values, including:
        - BOOLEAN_FIELDS: Handling boolean field types with True, False, and '0' values.
        - FLOAT_FIELDS: Handling float field types with float and numeric input.
        - TEXT_FIELDS: Handling text field types with text and boolean input.
        - MANY2ONE_FIELDS: Handling many2one field types by mapping external values to
          Odoo records.
        - Handling other field types (Many2many) by returning the input value.

        The test cases verify that '_prepare_simple_value' correctly processes input values
        and returns the expected results based on the field type and input value.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # check if field_type in BOOLEAN_FIELDS
        result_1 = instance._prepare_simple_value(
            self.product_ecommerce_field_available_for_order, True
        )
        self.assertEqual(result_1, True)

        result_2 = instance._prepare_simple_value(
            self.product_ecommerce_field_available_for_order, False
        )
        self.assertEqual(result_2, False)

        result_3 = instance._prepare_simple_value(
            self.product_ecommerce_field_available_for_order, '0'
        )
        self.assertEqual(result_3, False)

        # check if field_type in FLOAT_FIELDS
        result_4 = instance._prepare_simple_value(
            self.product_ecommerce_field_template_weight, '1.15'
        )
        self.assertEqual(result_4, 1.15)

        result_5 = instance._prepare_simple_value(
            self.product_ecommerce_field_template_weight, '0'
        )
        self.assertEqual(result_5, 0)

        result_6 = instance._prepare_simple_value(
            self.product_ecommerce_field_template_weight, False
        )
        self.assertEqual(result_6, 0)

        # check if field_type in TEXT_FIELDS
        result_7 = instance._prepare_simple_value(self.product_ecommerce_field_1, 'ext_value')
        self.assertEqual(result_7, 'ext_value')

        result_8 = instance._prepare_simple_value(self.product_ecommerce_field_1, False)
        self.assertIsNone(result_8)

        # check if field_type in MANY2ONE_FIELDS
        result_8 = instance._prepare_simple_value(
            self.product_ecommerce_field_default_category, False
        )
        self.assertEqual(result_8, False)

        result_9 = instance._prepare_simple_value(
            self.product_ecommerce_field_default_category, '0'
        )
        self.assertEqual(result_9, False)

        result_10 = instance._prepare_simple_value(
            self.product_ecommerce_field_default_category, 'Test Category'
        )
        self.assertEqual(result_10, self.product_public_category.id)

        result_10 = instance._prepare_simple_value(
            self.product_ecommerce_field_default_category, 'Test Category_New'
        )
        new_category = self.env['product.public.category'].search(
            [('name', '=', 'Test Category_New')]
        )
        self.assertEqual(result_10, new_category.id)

        # check if field_type in other fields(Many2many)
        result_11 = instance._prepare_simple_value(
            self.product_ecommerce_field_collections, 'ext_value'
        )
        self.assertEqual(result_11, 'ext_value')

    # integration/models/fields/receive_fields.py
    def test_get_translatable_field_value(self):
        """
        Test the '_get_translatable_field_value' method.

        This test case covers the '_get_translatable_field_value' method, which retrieves
        translatable field values from the external system, converts them to Odoo format,
        and returns them in a dictionary.

        It involves the following steps:
        - Creating an instance of the tested class.
        - Mocking the '_get_value' method to simulate the retrieval of an API value.
        - Mocking the 'convert_translated_field_to_odoo_format' method to simulate the
          conversion of API value to ERP value.

        The test case verifies that '_get_translatable_field_value' correctly retrieves, converts,
        and structures the translatable field value, returning it in a dictionary with the
        corresponding ERP field name.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        instance._get_value = MagicMock(return_value="api_value")
        instance.convert_translated_field_to_odoo_format = MagicMock(return_value="erp_value")

        result = instance._get_translatable_field_value(self.product_ecommerce_field_description)
        self.assertEqual(result, {'website_description': 'erp_value'})

    # integration/models/fields/receive_fields.py
    def test_get_python_method_value(self):
        """
        Test the '_get_python_method_value' method.

        This test case covers the '_get_python_method_value' method, which calls a Python method
        defined on the Odoo model to retrieve a computed field value.

        It involves the following steps:
        - Creating an instance of the tested class.
        - Mocking the '_compute_field_value_using_python_method' method to simulate the computation
          of the field value.

        The test case verifies that '_get_python_method_value' correctly invokes the Python method
        and returns its result.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        instance._compute_field_value_using_python_method = MagicMock(return_value="result")

        result = instance._get_python_method_value(self.product_ecommerce_field_1)
        self.assertEqual(result, "result")

    # integration/models/fields/receive_fields.py
    def test_calculate_receive_fields(self):
        """
        Test the 'calculate_receive_fields' method.

        This test case covers the 'calculate_receive_fields' method, which calculates and returns
        a dictionary of field values to be received from the external system. The method sets the
        'active' field to True when 'odoo_obj' is not present and includes additional fields based
        on the 'calculate_fields' method.

        It involves the following steps:
        - Creating an instance of the tested class.
        - Mocking the 'calculate_fields' method to simulate field calculations.
        - Setting different return values for 'calculate_fields' to test both cases when 'odoo_obj'
          exists and doesn't exist.

        The test case verifies that 'calculate_receive_fields' correctly calculates and structures
        field values based on 'calculate_fields' and sets 'active' to True when 'odoo_obj'
        is not present.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # Mock the calculate_fields method
        instance.calculate_fields = MagicMock()

        # Set a return value for calculate_fields
        instance.calculate_fields.return_value = {}

        # check if odoo_obj is not exist
        result_1 = instance.calculate_receive_fields()
        self.assertEqual(result_1, {'active': True})

        # Reset odoo_obj to False
        instance.odoo_obj = True

        # Set a new return value for calculate_fields
        instance.calculate_fields.return_value = {}

        # check if odoo_obj is exist
        result_2 = instance.calculate_receive_fields()
        self.assertEqual(result_2, {})

    # integration/models/fields/receive_fields.py
    @patch.object(IntegrationModelMixin, 'from_external')
    def test_find_attributes_in_odoo(self, mock_from_external):
        """
        Test the 'find_attributes_in_odoo' method.

        This test case covers the 'find_attributes_in_odoo' method, which searches for product
        attribute values in Odoo based on external attribute value IDs. The method calls the
        'from_external' method to retrieve corresponding Odoo attribute values and organizes
        them by attribute IDs.

        It involves the following steps:
        - Creating an instance of the tested class.
        - Mocking the 'from_external' method to simulate the retrieval of an Odoo attribute value.
        - Checking an attribute value against the 'find_attributes_in_odoo' method.

        The test case verifies that 'find_attributes_in_odoo' correctly identifies and organizes
        Odoo attribute values by attribute IDs based on external attribute value IDs.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        mock_from_external.return_value = self.product_attribute_value_white

        # check attribute value
        result = dict(instance.find_attributes_in_odoo(['attribute-value-Color-white']))
        self.assertEqual(
            result,
            {self.product_attribute_color.id: [self.product_attribute_value_white.id]}
        )

    # integration/models/fields/receive_fields.py
    @patch.object(IntegrationModelMixin, 'from_external')
    def test_find_categories_in_odoo(self, mock_from_external):
        """
        Test 'find_categories_in_odoo' method.

        Verify that the 'find_categories_in_odoo' method correctly maps external category IDs
        to Odoo category IDs.

        The test involves creating an instance of the tested class, mocking the 'from_external'
        method to simulate the retrieval of an Odoo category, and checking a category value against
        the 'find_categories_in_odoo' method. The test ensures that the method returns the
        expected Odoo category IDs.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        mock_from_external.return_value = self.product_public_category

        # check category value
        result = instance.find_categories_in_odoo(self.integration_product_public_category_external)
        self.assertEqual(result, [self.product_public_category.id])

    # integration/models/fields/receive_fields.py
    @patch.object(SaleIntegration, 'convert_external_tax_to_odoo')
    def test_get_odoo_tax_from_external(self, mock_convert_external_tax_to_odoo):
        """
        Test '_get_odoo_tax_from_external' method.

        Verify that the '_get_odoo_tax_from_external' method correctly retrieves an Odoo tax
        from an external tax value.

        The test involves creating an instance of the tested class, mocking the
        'convert_external_tax_to_odoo' method to simulate the conversion of an external tax
        value to an Odoo tax, and checking the method's behavior when the Odoo tax exists
        and when it doesn't. The test ensures that the method raises an 'ApiImportError'
        when the Odoo tax is not found.
        """
        # create instance
        instance = self.create_instance(self.ProductProduct, json.loads(pt_pp_1))

        # mock methods
        mock_convert_external_tax_to_odoo.return_value = self.tax_1

        # check if erp_tax is exist
        result_1 = instance._get_odoo_tax_from_external('tax_1')
        self.assertEqual(result_1, self.tax_1)

        # check if erp_tax is not exist
        mock_convert_external_tax_to_odoo.return_value = False
        with self.assertRaises(ApiImportError):
            instance._get_odoo_tax_from_external('tax_not_exist')
