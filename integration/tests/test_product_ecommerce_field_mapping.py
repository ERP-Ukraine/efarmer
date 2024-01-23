# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import patch

from ..models.fields.product_ecommerce_field_mapping import \
    ProductEcommerceFieldMapping
from .config.intuit_case import OdooIntegrationInit


class TestProductEcommerceFieldMapping(OdooIntegrationInit):

    def setUp(self):
        super(TestProductEcommerceFieldMapping, self).setUp()

        # Creating product.product ecommerce field
        self.pp_ecommerce_field_description = self.env.ref(
            'integration.product_pr_ecommerce_field_description')
        self.pp_ecommerce_field_mapping_description = self.env.ref(
            'integration.product_pr_ecommerce_field_mapping_description')

    # integration/models/fields/product_ecommerce_field_mapping.py
    def test_onchange_ecommerce_field_id(self):
        """
        Test the '_onchange_ecommerce_field_id' method.

        This test verifies that the '_onchange_ecommerce_field_id' method correctly updates
        the 'default_for_update' attribute when changing the selected e-commerce field.

        1. Initially, we change the 'default_for_update' attribute of
           'product_variant_ecommerce_field_1' to False.
        2. We then confirm that 'default_for_update' is True for
           'product_ecommerce_field_mapping_2.ecommerce_field_id'.
        3. Next, we change the 'ecommerce_field_id' of 'product_ecommerce_field_mapping_2' to
           'product_variant_ecommerce_field_1' and call the '_onchange_ecommerce_field_id' method.
        4. Finally, we check if the 'default_for_update' attribute of
           'product_ecommerce_field_mapping_2.ecommerce_field_id' is updated to False.

        This test ensures that the method behaves correctly when changing e-commerce fields
        and updating their attributes.
        """
        # change default_for_update in product_variant_ecommerce_field_1
        self.product_variant_ecommerce_field_1.write({
            'default_for_update': False,
        })

        # Check default_for_update is True
        result_1 = self.product_ecommerce_field_mapping_2.ecommerce_field_id.default_for_update
        self.assertTrue(result_1)

        # change ecomerce field in product_ecommerce_field_mapping_2
        self.product_ecommerce_field_mapping_2.write({
            'ecommerce_field_id': self.product_variant_ecommerce_field_1.id,
        })

        # call onchange method
        self.product_ecommerce_field_mapping_2._onchange_ecommerce_field_id()

        # check if default_for_update is changed
        result_2 = self.product_ecommerce_field_mapping_2.ecommerce_field_id.default_for_update
        self.assertFalse(result_2)

    # integration/models/fields/product_ecommerce_field_mapping.py
    def test_create(self):
        """
        Test the 'create' method of product.ecommerce.field.mapping.

        This test case checks the behavior of the 'create' method when creating instances of
        product.ecommerce.field.mapping. It verifies that the 'send_on_update' and
        'receive_on_import' fields are correctly set based on the 'default_for_update' and
        'default_for_import' attributes of the associated product.ecommerce.field.

        The test follows these steps:
        1. Creates an item in 'product.ecommerce.field' with specific attributes.
        2. Creates an item in 'product.ecommerce.field.mapping' related to the created field.
        3. Asserts that 'send_on_update' and 'receive_on_import' are set to True
           for the created mapping.

        Then, it changes the 'default_for_update' attribute of the field, and:
        4. Creates a new item in 'product.ecommerce.field.mapping' related to the same field.
        5. Asserts that 'send_on_update' is set to False and 'receive_on_import' to True
           for the new mapping.

        This test ensures that the 'create' method correctly sets the 'send_on_update'
        and 'receive_on_import' fields based on the 'default_for_update' and 'default_for_import'
        attributes of the associated field.
        """
        # creating item for product.ecommerce.field
        ecommerce_field = self.env['product.ecommerce.field'].create({
            'name': 'Test',
            'technical_name': 'code',
            'type_api': 'no_api',
            'value_converter': 'simple',
            'odoo_model_id': self.env.ref('product.model_product_template').id,
            'odoo_field_id': self.env.ref('product.field_product_template__barcode').id,
            'default_for_update': True,
            'default_for_import': True,
        })

        # creating item for product.ecommerce.field.mapping
        mapping_1 = self.env['product.ecommerce.field.mapping'].create({
            'name': 'Test Mapping',
            'ecommerce_field_id': ecommerce_field.id,
            'integration_id': self.integration_no_api_1.id,
        })

        self.assertTrue(mapping_1.send_on_update)
        self.assertTrue(mapping_1.receive_on_import)

        # changing default_for_update for ecommerce_field
        ecommerce_field.write({'default_for_update': False})

        # creating item for product.ecommerce.field.mapping with default_for_update = False
        new_mapping = self.env['product.ecommerce.field.mapping'].create({
            'name': 'New Test Mapping',
            'ecommerce_field_id': ecommerce_field.id,
            'integration_id': self.integration_no_api_1.id,
        })

        self.assertFalse(new_mapping.send_on_update)
        self.assertTrue(new_mapping.receive_on_import)

    # integration/models/fields/product_ecommerce_field_mapping.py
    @patch.object(ProductEcommerceFieldMapping, '_search_translatable_fields')
    def test_get_translatable_template_api_names(self, mock_search_translatable_fields):
        """
        Test the 'get_translatable_template_api_names' method of product.ecommerce.field.mapping.

        This test case verifies that the 'get_translatable_template_api_names' method correctly
        filters and returns the technical names of fields related to product templates
        that are translatable.

        The test follows these steps:
        1. Mocks the '_search_translatable_fields' method to return specific mappings
           related to descriptions.
        2. Calls the 'get_translatable_template_api_names' method.
        3. Asserts that the returned list contains the technical name 'description'.

        This test ensures that the method filters the mappings correctly and returns the expected
        translatable field names related to product templates.
        """
        mappings = self.product_ecommerce_field_mapping_description

        # mock search method
        mock_search_translatable_fields.return_value = mappings

        result = self.product_ecommerce_field_mapping_description \
            .get_translatable_template_api_names()
        self.assertEqual(result, ['description'])

    # integration/models/fields/product_ecommerce_field_mapping.py
    @patch.object(ProductEcommerceFieldMapping, '_search_translatable_fields')
    def test_get_translatable_variant_api_names(self, mock_search_translatable_fields):
        """
        Test the 'get_translatable_variant_api_names' method.

        This test case verifies that the 'get_translatable_variant_api_names' method correctly
        returns a list of technical field names for translatable fields in the product
        product model.

        The test follows these steps:
        1. Mocks the '_search_translatable_fields' method to return a predefined set of mappings,
           using product template field.
        2. Calls the 'get_translatable_variant_api_names' method.
        3. Asserts that the returned list is empty since product template fields are not relevant
           for product variants.

        4. Mocks the '_search_translatable_fields' method again, this time using product product
           field mappings.
        5. Calls the 'get_translatable_variant_api_names' method.
        6. Asserts that the returned list contains the expected technical field names,
           in this case, 'description'.

        This test ensures that the method accurately identifies and returns technical
        field names for translatable fields in the product product model and correctly handles
        mappings from both product template and product product fields.
        """
        # mock search method, using product template field
        mappings_pt = self.product_ecommerce_field_mapping_description

        # mock search method
        mock_search_translatable_fields.return_value = mappings_pt

        result_1 = self.product_ecommerce_field_mapping_description \
            .get_translatable_variant_api_names()
        self.assertEqual(result_1, [])

        # mock search method, using product product field
        mappings_pp = self.pp_ecommerce_field_mapping_description

        # mock search method
        mock_search_translatable_fields.return_value = mappings_pp

        result_2 = self.product_ecommerce_field_mapping_description \
            .get_translatable_variant_api_names()
        self.assertEqual(result_2, ['description'])

    # integration/models/fields/product_ecommerce_field_mapping.py
    def test_search_translatable_fields(self):
        """
        Test the '_search_translatable_fields' method of product.ecommerce.field.mapping.

        This test case verifies that the '_search_translatable_fields' method correctly filters and
        returns mappings related to translatable fields with the value converter
        'translatable_field'.

        The test follows these steps:
        1. Searches for all mappings in the system that have the 'value_converter'
           set to 'translatable_field'.
        2. Calls the '_search_translatable_fields' method without specifying an integration.
        3. Asserts that the returned mapping IDs match the ones found in step 1.

        Additionally, it tests the method for a specific integration:
        1. Searches for mappings in the integration 'integration_no_api_2' that have
           the 'value_converter' set to 'translatable_field'.
        2. Calls the '_search_translatable_fields' method with the context set
           to the 'integration_no_api_2' ID.
        3. Asserts that the returned mapping IDs match the ones found in step 1
           for the specific integration.

        This test ensures that the method correctly filters and returns mappings related to
        translatable fields for both all integrations and a specific integration context.
        """
        obj = self.env['product.ecommerce.field.mapping']

        mapping_ids = obj.search([]).filtered(
            lambda x: x.ecommerce_field_id.value_converter == 'translatable_field'
        )

        result = obj._search_translatable_fields()
        self.assertEqual(result, mapping_ids)

        # testing for specific integration
        mapping_ids = obj.search([('integration_id', '=', self.integration_no_api_2.id)]).filtered(
            lambda x: x.ecommerce_field_id.value_converter == 'translatable_field'
        )

        result_2 = obj.with_context(
            integration_id=self.integration_no_api_2.id)._search_translatable_fields()
        self.assertEqual(result_2, mapping_ids)
