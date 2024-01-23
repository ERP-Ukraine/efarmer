# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import MagicMock, patch

from ...integration.models.fields import SendFields
from ...integration.models.fields.send_fields_product_product import \
    ProductProductSendMixin
from ..models.integration_model_mixin import IntegrationModelMixin
from .config.intuit_case import OdooIntegrationInit


class SendFieldsProductProductTest(SendFields, ProductProductSendMixin):
    pass


class TestSendFieldsProductProduct(OdooIntegrationInit):

    def setUp(self):
        super(TestSendFieldsProductProduct, self).setUp()

    def create_instance(self, product_obj):
        return SendFieldsProductProductTest(
            self.integration_no_api_1,
            product_obj,
        )

    # integration/models/fields/send_fields_product_product.py
    @patch.object(IntegrationModelMixin, 'to_export_format_or_export')
    def test_convert_to_external(self, mock_to_export_format_or_export):
        """
        Test the 'convert_to_external' method.

        Testing the convert_to_external method under various conditions, including:
        - Creating template attribute lines and assigning template attribute values.
        - Mocking the ensure_odoo_record method.
        - Mocking the to_export_format_or_export method.
        - Mocking the calculate_send_fields method.
        - Verifying the expected result when exclude_from_synchronization is False.
        - Verifying the expected result when exclude_from_synchronization is True.

        It checks that the convert_to_external method correctly generates the expected
        result based on product attributes and synchronization settings.
        """
        # Creating template attribute lines
        tmpl_attr_lines = self.env['product.template.attribute.line'].create(
            {
                'attribute_id': self.product_attribute_color.id,
                'product_tmpl_id': self.product_pt_1.id,
                'value_ids': [(6, 0, self.product_attribute_color.value_ids.ids)],
            }
        )

        # Assigning template attribute value
        self.product_pt_1.product_variant_id.write(
            {
                'product_template_attribute_value_ids': [
                    (6, 0, tmpl_attr_lines.product_template_value_ids[0].ids)
                ],
            }
        )

        # Creating instance
        self.instance_pt_pp_1 = self.create_instance(
            self.product_pt_1.product_variant_id,
        )

        # Mocking ensure_odoo_record method
        self.instance_pt_pp_1.ensure_odoo_record = MagicMock(return_value=None)

        # Mocking to_export_format_or_export method
        mock_to_export_format_or_export.return_value = {'color': 'white'}

        # Mocking calculate_send_fields method
        self.instance_pt_pp_1.calculate_send_fields = MagicMock(return_value='expected_fields')

        result = self.instance_pt_pp_1.convert_to_external()
        expected_result = {
            'id': self.product_pt_1.product_variant_id.id,
            'external_id': self.instance_pt_pp_1.external_id,
            'attribute_values': [{'color': 'white'}],
            'fields': 'expected_fields'
        }
        self.assertEqual(result, expected_result)

        # Checking if exclude_from_synchronization is True
        self.product_attribute_color.value_ids.write({'exclude_from_synchronization': True})
        result = self.instance_pt_pp_1.convert_to_external()
        expected_result = {
            'id': self.product_pt_1.product_variant_id.id,
            'external_id': self.instance_pt_pp_1.external_id,
            'attribute_values': [],
            'fields': 'expected_fields'
        }
        self.assertEqual(result, expected_result)
