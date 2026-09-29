# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL
from odoo.addons.integration_shopify.shopify.resources.shop import Shop


@tagged('post_install', '-at_install')
class TestShopifyShopContact(TransactionCase):
    """Shop country comes from shopAddress; product tags from QueryRoot.productTags."""

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def test_shop_body_uses_shop_address_not_billing_address(self):
        body = GraphQLTemplate.SHOP_BODY

        self.assertIn('shopAddress', body)
        self.assertIn('countryCodeV2', body)
        self.assertNotIn('billingAddress', body)
        self.assertNotIn('firstName', body)
        self.assertNotIn('lastName', body)
        self.assertNotIn('productTags', body)

    def test_country_code_reads_shop_address(self):
        shop = self._gql().Shop.set(
            id='gid://shopify/Shop/1',
            shopAddress={'countryCodeV2': 'PL', 'country': 'Poland'},
        )

        self.assertEqual(shop.country_code, 'PL')

    def test_shop_address_exposes_every_field(self):
        shop = self._gql().Shop.set(
            id='gid://shopify/Shop/1',
            shopAddress={
                'country': 'Poland',
                'countryCodeV2': 'PL',
                'city': 'Warsaw',
                'zip': '00-001',
                'provinceCode': 'MZ',
            },
        )

        address = shop.shop_address

        self.assertEqual(address.country, 'Poland')
        self.assertEqual(address.country_code, 'PL')
        self.assertEqual(address.city, 'Warsaw')
        self.assertEqual(address.zip, '00-001')
        self.assertEqual(address.province_code, 'MZ')

    def test_shop_address_missing_fields_are_empty(self):
        shop = self._gql().Shop.set(id='gid://shopify/Shop/1')

        address = shop.shop_address

        self.assertEqual(address.country, '')
        self.assertEqual(address.country_code, '')
        self.assertEqual(address.city, '')
        self.assertEqual(address.zip, '')
        self.assertEqual(address.province_code, '')

    def test_product_tags_query_root_when_missing(self):
        payload = {
            'data': {
                'productTags': {
                    'nodes': ['car', 'cat'],
                    'pageInfo': {'endCursor': None, 'hasNextPage': False},
                },
            },
        }
        shop = self._gql().Shop.set(id='gid://shopify/Shop/1')

        with patch.object(Shop, 'execute', return_value=payload) as mocked:
            tags = shop.product_tags

        mocked.assert_called_once()
        query = mocked.call_args[0][0]
        self.assertIn('productTags(first: 250, after: $cursor)', query)
        self.assertIsNone(mocked.call_args.kwargs['variables']['cursor'])
        self.assertEqual(tags, ['car', 'cat'])
        self.assertEqual(shop.product_tags, ['car', 'cat'])
        mocked.assert_called_once()

    def test_get_product_tags_pages_past_the_first_250(self):
        first_page = {'data': {'productTags': {
            'nodes': ['car'],
            'pageInfo': {'endCursor': 'cursor1', 'hasNextPage': True},
        }}}
        second_page = {'data': {'productTags': {
            'nodes': ['cat'],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}
        shop = self._gql().Shop.set(id='gid://shopify/Shop/1')

        with patch.object(Shop, 'execute', side_effect=[first_page, second_page]) as mocked:
            tags = shop.get_product_tags()

        self.assertEqual(mocked.call_count, 2)
        self.assertIsNone(mocked.call_args_list[0].kwargs['variables']['cursor'])
        self.assertEqual(mocked.call_args_list[1].kwargs['variables']['cursor'], 'cursor1')
        self.assertEqual(tags, ['car', 'cat'])
