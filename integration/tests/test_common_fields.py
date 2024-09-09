# See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock

from odoo.exceptions import UserError

from .config.integration_init import OdooIntegrationInit
from ...integration.models.fields import CommonFields


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
        self.product_ecommerce_field_1.converter_action_name = "_get_simple_value"

        # Mock _get_ecommerce_field in SendFields class
        self.instanse_pt_1._get_simple_value = MagicMock(return_value=True)

        # Check when value_converter is exist
        self.assertEqual(
            self.instanse_pt_1.calculate_field_value(self.product_ecommerce_field_1), True
        )

        # Check when converter is not exist
        self.product_ecommerce_field_1.converter_action_name = "_get_non_existent_value"
        with self.assertRaises(AttributeError):
            self.instanse_pt_1.calculate_field_value(self.product_ecommerce_field_1)

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
