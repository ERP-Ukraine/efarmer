# See LICENSE file for full copyright and licensing details.

import re

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate

from .init_integration_shopify import IntegrationShopifyBase


PRODUCT_CODE = '10203545100500'
PRODUCT_HANDLE = 'e-guitar-test-az1u28399'


def _top_level_fields(body: str) -> list:
    """
    Return the field names selected at the top level of a GraphQL selection body.

    :param body: GraphQL selection set without the enclosing braces
    :return: list of field names outside any nested selection
    """
    body = re.sub(r'\([^)]*\)', '', body)
    depth = 0
    result = []

    for token in re.findall(r'[{}]|\w+', body):
        if token == '{':
            depth += 1
        elif token == '}':
            depth -= 1
        elif depth == 0:
            result.append(token)

    return result


@tagged('post_install', '-at_install')
class TestShopifyProductHandle(IntegrationShopifyBase):
    """The product handle is read on import and reaches the Odoo field the customer maps it to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Taxonomy category required by the product test data
        cls.env['external.taxonomy.category'].create({
            'name': 'Electric Guitars',
            'code': 'ae-2-8-7-2-4',
            'integration_id': cls.integration.id,
        })

        cls.handle_field = cls.env.ref('integration_shopify.shopify_ecommerce_field_handle')

    def _map_handle_field(self):
        self.handle_field.odoo_field_id = self.env.ref('product.field_product_template__description_sale')

        return self.handle_field._ensure_mapping(self.integration.id)

    def _import_external_template(self):
        external_template, __, errors, __ = self.integration._import_external_product(
            [PRODUCT_CODE],
            try_to_map=False,
            raise_error=False,
        )
        self.assertFalse(errors)

        return external_template

    def test_product_query_selects_handle(self):
        self.assertIn('handle', _top_level_fields(GraphQLTemplate.PRODUCT_BODY))

    def test_handle_field_is_not_mapped_by_default(self):
        mapping = self.handle_field.with_context(active_test=False).mapping_ids \
            .filtered(lambda x: x.integration_id == self.integration)
        self.assertFalse(mapping)

        mapping = self._map_handle_field()
        self.assertTrue(mapping.active)
        self.assertTrue(mapping.import_enabled)
        self.assertFalse(mapping.export_enabled)

    @mute_logger('odoo.addons.integration.tools')
    def test_handle_imported_into_mapped_field(self):
        self._map_handle_field()
        external_template = self._import_external_template()

        data = external_template.calculate_import_fields_data()
        self.assertEqual(data['description_sale'], PRODUCT_HANDLE)

        template = external_template.import_one_product(import_images=False)
        self.assertEqual(template.description_sale, PRODUCT_HANDLE)

    def test_handle_is_not_exported(self):
        self._map_handle_field()
        template = self.env['product.template'].create({
            'name': 'New product',
            'description_sale': 'custom-handle',
        })

        data = template.calculate_export_fields_data(self.integration.id)
        self.assertNotIn('handle', data)

        # The first export of a product sends every active mapping whatever its export flag
        data = template.with_context(integration_first_time_export=True) \
            .calculate_export_fields_data(self.integration.id)
        self.assertNotIn('handle', data)
