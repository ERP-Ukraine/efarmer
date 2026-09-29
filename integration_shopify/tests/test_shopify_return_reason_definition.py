# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL


@tagged('post_install', '-at_install')
class TestShopifyReturnReasonDefinition(TransactionCase):
    """Return ingest prefers ReturnReasonDefinition, falling back to the enum when absent."""

    LINE_ITEM = {
        'id': 'gid://shopify/FulfillmentLineItem/9',
        'lineItem': {
            'id': 'gid://shopify/LineItem/8',
            'sku': 'SKU-1',
        },
    }

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def _line(self, **kwargs):
        payload = {
            'id': 'gid://shopify/ReturnLineItem/1',
            'quantity': 1,
            'refundableQuantity': 1,
            'refundedQuantity': 0,
            'returnReasonNote': '',
            'fulfillmentLineItem': self.LINE_ITEM,
        }
        payload.update(kwargs)

        return self._gql().ReturnLineItem.set(**payload)

    def test_return_body_selects_reason_definition_and_keeps_enum(self):
        body = GraphQLTemplate.ORDER_RETURN_BODY

        self.assertIn('returnReasonDefinition', body)
        self.assertIn('handle', body)
        self.assertIn('name', body)
        # returnReason is still requested: it is the only fallback source when
        # a return has no definition (undocumented legacy/custom reasons).
        self.assertIn('returnReason', body)

    def test_to_odoo_format_prefers_definition_name(self):
        line = self._line(
            returnReason='COLOR',
            returnReasonDefinition={
                'handle': 'too-bright',
                'name': 'Color too bright',
            },
        )

        self.assertEqual(line.to_odoo_format()['return_reason'], 'Color too bright')

    def test_to_odoo_format_falls_back_to_enum_map(self):
        line = self._line(returnReason='UNWANTED')

        self.assertEqual(
            line.to_odoo_format()['return_reason'],
            'Customer changed their mind',
        )
