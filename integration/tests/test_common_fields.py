# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import MagicMock

from odoo.exceptions import UserError

from ...integration.models.fields import CommonFields
from .config.intuit_case import OdooIntegrationInit


class TestCommonFields(OdooIntegrationInit):
    def setUp(self):
        super(TestCommonFields, self).setUp()

        self.instanse_pt_1 = self.create_instance(
            self.product_pt_1,
        )

        self.instanse_pt_pp_1 = self.create_instance(
            self.product_pt_1.product_variant_id,
        )

        self.instanse_pp_2 = self.create_instance(
            self.product_pp_2,
        )

    def create_instance(self, product_obj):
        return CommonFields(
            self.integration_no_api_1,
            product_obj,
            False,
        )

    # integration/integration/models/fields/common_fields.py
    def test_calculate_field_value(self):
        """
        Test the 'calculate_field_value' method.

        This test case verifies that the 'calculate_field_value' method correctly handles
        different scenarios based on the 'value_converter' attribute of
        the 'product_ecommerce_field_1' field.

        The test follows these steps:

        1. Mocks the 'value_converter' attribute of 'product_ecommerce_field_1' to be 'simple'.
        2. Mocks the '_get_simple_value' method in the 'SendFields' class to return 'True'.
        3. Calls the 'calculate_field_value' method with 'product_ecommerce_field_1'.
        4. Asserts that the method returns 'True' as expected.

        5. Mocks the 'value_converter' attribute of 'product_ecommerce_field_1'
           to be 'non_existent_converter'.
        6. Calls the 'calculate_field_value' method with 'product_ecommerce_field_1'.
        7. Asserts that the method raises an 'AttributeError' since there is no method
           defined for the 'non_existent_converter'.

        This test ensures that the 'calculate_field_value' method correctly processes
        the value conversion based on the 'value_converter' attribute and raises an exception
        when an unsupported converter is encountered.
        """
        # Mock value_converter
        self.product_ecommerce_field_1 = MagicMock()
        self.product_ecommerce_field_1.value_converter = "simple"

        # Mock _get_ecommerce_field in SendFields class
        self.instanse_pt_1._get_simple_value = MagicMock(return_value=True)

        # Check when value_converter is exist
        self.assertEqual(
            self.instanse_pt_1.calculate_field_value(self.product_ecommerce_field_1), True
        )

        # Check when converter is not exist
        self.product_ecommerce_field_1.value_converter = "non_existent_converter"
        with self.assertRaises(AttributeError):
            self.instanse_pt_1.calculate_field_value(self.product_ecommerce_field_1)

    # integration/integration/models/fields/common_fields.py
    def test_get_ecommerce_field(self):
        """
        Test the '_get_ecommerce_field' method.

        This test case checks if the '_get_ecommerce_field' method correctly retrieves
        the eCommerce field associated with the given 'field_name' for both product templates
        and product variants.

        The test covers the following scenarios:

        1. Checking for an existing field ('default_code') for a product template.
           Expects the correct eCommerce field.
        2. Checking for an existing field ('default_code') for a product variant.
           Expects the correct eCommerce field.
        3. Checking for a non-existent field ('wrong') for a product template. Expects 'False'.
        4. Checking for a non-existent field ('wrong') for a product variant. Expects 'False'.
        """
        # Checking existing field for product template
        self.assertEqual(
            self.instanse_pt_1._get_ecommerce_field("default_code"), self.product_ecommerce_field_2
        )

        # Checking existing field for product variant
        self.assertEqual(
            self.instanse_pt_pp_1._get_ecommerce_field("default_code"),
            self.product_variant_ecommerce_field_1,
        )

        # Checking wrong field for product template
        self.assertFalse(self.instanse_pt_1._get_ecommerce_field("wrong"))

        # Checking wrong field for product variant
        self.assertFalse(self.instanse_pt_pp_1._get_ecommerce_field("wrong"))

    # integration/integration/models/fields/common_fields.py
    def test_convert_weight_uom(self):
        """
        Test the '_convert_weight_uom' method.

        This test case checks the conversion of product weight from one
        unit of measure (UOM) to another.

        It tests various scenarios, including:
        1. Converting weight from 'kg' to default UOM (kg).
        2. Converting weight from an empty UOM to default UOM (kg).
        3. Converting weight from 'lb' to default UOM (kg).
        4. Converting weight from 'oz' to default UOM (kg).
        5. Converting weight from 'oz' to default UOM (kg) with 'is_import' set to True.
        6. Attempting to convert weight with an unsupported UOM ('wrong').
        """

        def _convert_weight_uom(unit_measure, is_import=False):
            return self.instanse_pp_2._convert_weight_uom(
                self.product_pp_1.weight,
                unit_measure,
                is_import,
            )

        self.product_pp_1.write({"weight": 1.56})

        self.assertEqual(_convert_weight_uom("kg"), 1.56)
        self.assertEqual(_convert_weight_uom(""), 1.56)
        self.assertEqual(_convert_weight_uom("lb"), 3.44)
        self.assertEqual(_convert_weight_uom("oz"), 55.03)
        self.assertEqual(_convert_weight_uom("oz", is_import=True), 0.05)
        with self.assertRaises(UserError):
            _convert_weight_uom("wrong")
