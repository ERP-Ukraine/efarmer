# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import patch

from odoo.exceptions import UserError

from ...integration.exceptions import NotMappedToExternal
from ...integration.models.fields import SendFields
from .config.intuit_case import OdooIntegrationInit


class TestSendFields(OdooIntegrationInit):

    def setUp(self):
        super(TestSendFields, self).setUp()

        self.instance_pt_1 = self.create_instance(self.product_pt_1)
        self.instance_pp_2 = self.create_instance(self.product_pp_2)
        self.instance_pt_pp_2 = self.create_instance(self.product_pt_1.product_variant_id)

    def create_instance(self, product_obj):
        return SendFields(
            self.integration_no_api_1,
            product_obj,
        )

    # integration/models/fields/send_fields.py
    def test_ensure_mapped(self):
        """
        Test the 'ensure_mapped' method.

        This test checks the behavior of the 'ensure_mapped' method in different scenarios:
        1. When both 'odoo_obj' and 'external_id' are True, it should return True.
        2. When 'external_id' is False, it should return False.
        3. When 'odoo_obj' is False, it should return False.
        """
        # Check if odoo_obj and external_id are True
        self.assertEqual(
            self.instance_pt_1.ensure_mapped(),
            True,
        )

        # Check if external_id is False
        self.instance_pt_1.external_id = False

        self.assertEqual(
            self.instance_pt_1.ensure_mapped(),
            False,
        )

        # Check if odoo_obj is False
        self.instance_pt_1.odoo_obj = False
        self.instance_pt_1.external_id = self.external_pt_1

        self.assertEqual(
            self.instance_pt_1.ensure_mapped(),
            False,
        )

    # integration/models/fields/send_fields.py
    def test_ensure_odoo_record(self):
        """
        Test the 'ensure_odoo_record' method.

        This test verifies the behavior of the 'ensure_odoo_record' method in different scenarios:
        1. When 'odoo_obj' is True, it should not raise any exceptions.
        2. When 'odoo_obj' is False, it should raise a 'UserError' exception.
        """
        # Check if odoo_obj is True
        self.assertEqual(
            self.instance_pt_1.ensure_odoo_record(),
            None,
        )

        # Check if odoo_obj is False
        self.instance_pt_1.odoo_obj = False

        with self.assertRaises(UserError):
            self.instance_pt_1.ensure_odoo_record()

    # integration/models/fields/send_fields.py
    def test_ensure_external_code(self):
        """
        Test the 'ensure_external_code' method.

        This test evaluates the behavior of the 'ensure_external_code' method in
        different scenarios:
        1. When 'external_id' is True, it should not raise any exceptions.
        2. When 'external_id' is False, it should raise a 'NotMappedToExternal' exception.
        3. When 'odoo_obj' is False, it should raise a 'UserError' exception.
        """
        # Check if external_id is True
        self.assertEqual(
            self.instance_pt_1.ensure_external_code(),
            None,
        )

        # Check if external_id is False
        self.instance_pt_1.external_id = False
        with self.assertRaises(NotMappedToExternal):
            self.instance_pt_1.ensure_external_code()

        # Check if odoo_obj is False
        self.instance_pt_1.odoo_obj = False
        with self.assertRaises(UserError):
            self.instance_pt_1.ensure_external_code()

    # integration/models/fields/send_fields.py
    def test_convert_translated_field_to_integration_format(self):
        """
        Test the 'convert_translated_field_to_integration_format' method.

        This test verifies the behavior of the 'convert_translated_field_to_integration_format'
        method:
        1. It checks whether the method correctly returns the translated field value for
           the given 'field_name'.
        2. It tests the scenario when the provided 'field_name' is incorrect, and it expects an
           'AttributeError' to be raised.
        """
        self.assertEqual(
            self.instance_pt_1.convert_translated_field_to_integration_format(
                'name',
            ),
            'Test Product 1',
        )

        # Check if field_name is wrong
        with self.assertRaises(AttributeError):
            self.instance_pt_1.convert_translated_field_to_integration_format(
                'wrong_name',
            )

    # integration/models/fields/send_fields.py
    def test_update_external_id(self):
        """
        Test the '_update_external_id' method.

        This test covers the behavior of the '_update_external_id' method under
        different scenarios:
        1. When 'external_id' is True, it should return the 'code' of the external record.
        2. When 'try_to_external_record' method returns None, it should return None.
        3. When 'odoo_obj' is False, it should return None.
        """
        # Check if external_id is True
        self.assertEqual(
            self.instance_pt_1._update_external_id(),
            self.external_pt_1.code,
        )

        # Check if method try_to_external_record returns None
        with self.cr.savepoint(), patch.object(
            type(self.instance_pt_1.odoo_obj), 'try_to_external_record'
        ) as mock_try_to_external_record:
            mock_try_to_external_record.return_value = None
            self.assertIsNone(self.instance_pt_1._update_external_id())

        # Check if odoo_obj is False
        self.instance_pt_1.odoo_obj = False
        self.assertIsNone(self.instance_pt_1._update_external_id())

    # integration/models/fields/send_fields.py
    def test_get_simple_value(self):
        """
        Test the '_get_simple_value' method.

        This test evaluates the behavior of the '_get_simple_value' method:
        1. It checks if the method returns the correct result when 'product_ecommerce_field_1'
           is provided.
        2. It mocks the '_prepare_simple_value' method and checks if the method correctly handles
           its return value.
        """
        self.assertEqual(
            self.instance_pt_1._get_simple_value(self.product_ecommerce_field_1),
            {'code': 'barcode_1'},
        )

        with self.cr.savepoint(), patch.object(type(self.instance_pt_1), '_prepare_simple_value') \
                as mock_prepare_simple_value:
            mock_prepare_simple_value.return_value = ''
            self.assertEqual(
                self.instance_pt_1._get_simple_value(self.product_ecommerce_field_1),
                {'code': ''},
            )

    # integration/models/fields/send_fields.py
    def test_prepare_simple_value(self):
        """
        Test the '_prepare_simple_value' method.

        This test evaluates the behavior of the '_prepare_simple_value' method in
        various scenarios:
        1. When 'field_type' is 'char' and 'odoo_value' is a non-empty string, it should
           return the same string.
        2. When 'field_type' is 'char' and 'odoo_value' is False, it should return an empty string.
        3. When 'field_type' is 'wrong_char' and 'odoo_value' is False, it should return False.
        4. When 'field_type' is 'many2one' and 'odoo_value' is False, it should return False.
        5. When 'field_type' is 'many2one' and 'odoo_value' is a Many2one record, it should return
           the name of the record.
        """
        def _prepare_simple_value(field_name, field_type, odoo_value):
            return self.instance_pp_2._prepare_simple_value(
                field_name,
                field_type,
                odoo_value,
            )

        self.assertEqual(_prepare_simple_value('barcode', 'char', 'barcode_value'), 'barcode_value')
        self.assertEqual(_prepare_simple_value('barcode', 'char', False), '')
        self.assertEqual(_prepare_simple_value('barcode', 'wrong_char', False), False)
        self.assertEqual(_prepare_simple_value('barcode', 'many2one', False), '')

        uom_id = self.instance_pp_2.odoo_obj.uom_id
        self.assertEqual(_prepare_simple_value('oum_id', 'many2one', uom_id), 'Units')

    # integration/models/fields/send_fields.py
    def test_get_translatable_field_value(self):
        """
        Test the '_get_translatable_field_value' method.

        This test verifies the behavior of the '_get_translatable_field_value' method by mocking
        the 'convert_translated_field_to_integration_format' method and checking if it correctly
        constructs a dictionary with the expected API value.
        """
        with self.cr.savepoint(), patch.object(
            type(self.instance_pt_1), 'convert_translated_field_to_integration_format'
        ) as mock_convert_translated_field_to_integration_format:
            mock_convert_translated_field_to_integration_format.return_value = 'barcode_1'
            self.assertEqual(
                self.instance_pt_1._get_translatable_field_value(self.product_ecommerce_field_1),
                {'code': 'barcode_1'},
            )

            mock_convert_translated_field_to_integration_format.return_value = False
            self.assertEqual(
                self.instance_pt_1._get_translatable_field_value(self.product_ecommerce_field_1),
                {'code': ''},
            )

    # integration/models/fields/send_fields.py
    def test_calculate_send_fields(self):
        """
        Test the 'calculate_send_fields' method.

        This test evaluates the behavior of the 'calculate_send_fields' method in different
        scenarios:
        1. When 'external_code' is provided (not False), it should apply a specific domain filter
           and return the calculated fields.
        2. When 'external_code' is False, it should not apply any domain filter and return the same
           calculated fields.
        """
        with self.cr.savepoint(), patch.object(type(self.instance_pt_1), 'calculate_fields') \
                as mock_calculate_fields:
            mock_calculate_fields.return_value = {'code': 'barcode_1', 'sku': 'default_code_1'}
            self.assertEqual(
                self.instance_pt_1.calculate_send_fields(self.instance_pt_1.external_id),
                {'code': 'barcode_1', 'sku': 'default_code_1'},
            )

            self.assertEqual(
                self.instance_pt_1.calculate_send_fields(False),
                {'code': 'barcode_1', 'sku': 'default_code_1'},
            )

    # integration/models/fields/send_fields.py
    def test_get_price_by_send_tax_incl(self):
        """
        Test the 'get_price_by_send_tax_incl' method.

        This test evaluates the behavior of the 'get_price_by_send_tax_incl' method in different
        scenarios:
        1. It checks if the method correctly calculates the price when
           'integration.select_send_sale_price' is set to 'no_changes'.
        2. It mocks the 'compute_all' method to simulate tax calculations and verifies that the
           method returns the correct price
        when 'integration.select_send_sale_price' is set to 'tax_included'.
        3. It verifies that the method returns the correct price when
           'integration.select_send_sale_price' is set to 'tax_excluded'.
        """
        with self.cr.savepoint(), patch.object(type(self.integration_no_api_1),
                                               'get_settings_value') as mock_get_settings_value:
            mock_get_settings_value.return_value = '2'

            self.assertEqual(
                self.instance_pt_pp_2.get_price_by_send_tax_incl(
                    self.product_pt_1.product_variant_id.list_price
                ),
                15.00,
            )

            with self.cr.savepoint(), patch.object(type(self.tax_1),
                                                   'compute_all') as mock_compute_all:
                mock_compute_all.return_value = {
                    'total_excluded': 15.00,
                    'total_included': 16.50,
                }

                # Check if integration_no_api is tax_included
                self.integration_no_api_1.select_send_sale_price = 'tax_included'
                self.assertEqual(
                    self.instance_pt_pp_2.get_price_by_send_tax_incl(
                        self.product_pt_1.product_variant_id.list_price
                    ),
                    16.50,
                )

                # Check if integration_no_api is tax_excluded
                self.integration_no_api_1.select_send_sale_price = 'tax_excluded'
                self.assertEqual(
                    self.instance_pt_pp_2.get_price_by_send_tax_incl(
                        self.product_pt_1.product_variant_id.list_price
                    ),
                    15.00,
                )
