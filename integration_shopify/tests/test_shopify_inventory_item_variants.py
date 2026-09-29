# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate
from odoo.addons.integration_shopify.shopify.resources.inventory_item import InventoryItem
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL


@tagged('post_install', '-at_install')
class TestShopifyInventoryItemVariants(TransactionCase):
    """InventoryItem.variant is deprecated; get_variants() reads every variants.nodes entry,
    fetched only where needed (inventory levels), not on every InventoryItem query.
    """

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def test_inventory_item_body_does_not_fetch_variants(self):
        body = GraphQLTemplate.INVENTORY_ITEM_BODY

        self.assertNotIn('variants(', body)
        self.assertNotIn('variant {', body)

    def test_inventory_level_body_uses_variants_connection(self):
        body = GraphQLTemplate.INVENTORY_LEVEL_BODY

        self.assertIn('variants(first: 50)', body)
        self.assertIn('product {', body)

    def test_get_variants_reads_every_variants_node(self):
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/1',
            variants={
                'nodes': [{
                    'id': 'gid://shopify/ProductVariant/22',
                    'product': {
                        'id': 'gid://shopify/Product/11',
                    },
                }],
            },
        )

        variants = item.get_variants()

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].id_str, '22')
        self.assertEqual(variants[0].product_id, 11)
        self.assertEqual(variants[0].external_id, '11-22')
        self.assertEqual(
            [v.external_id for v in item._env.InventoryLevel.set(
                id='gid://shopify/InventoryLevel/9?inventory_item_id=1',
                item=item.to_dict(),
            ).get_variants()],
            ['11-22'],
        )

    def test_combined_listing_yields_every_sharing_variant(self):
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/3',
            variants={
                'nodes': [
                    {'id': 'gid://shopify/ProductVariant/22', 'product': {'id': 'gid://shopify/Product/11'}},
                    {'id': 'gid://shopify/ProductVariant/33', 'product': {'id': 'gid://shopify/Product/11'}},
                ],
            },
        )

        self.assertEqual([v.external_id for v in item.get_variants()], ['11-22', '11-33'])

    def test_missing_variants_yields_empty_list(self):
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/2',
            variants={'nodes': []},
        )

        self.assertEqual(item.get_variants(), [])

    def test_short_page_does_not_trigger_a_follow_up_query(self):
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/4',
            variants={'nodes': [
                {'id': 'gid://shopify/ProductVariant/22', 'product': {'id': 'gid://shopify/Product/11'}},
            ]},
        )

        with patch.object(InventoryItem, 'execute') as execute_mock:
            variants = item.get_variants()

        execute_mock.assert_not_called()
        self.assertEqual([v.external_id for v in variants], ['11-22'])

    def test_full_page_triggers_a_paginated_follow_up_query(self):
        """A page exactly PAGE_SIZE long is the truncation signal; get_variants()

        must then page a dedicated query against this one item instead of
        trusting the (possibly incomplete) embedded page.
        """
        page_size = GraphQLTemplate.INVENTORY_ITEM_VARIANTS_PAGE_SIZE
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/5',
            variants={'nodes': [
                {'id': f'gid://shopify/ProductVariant/{i}', 'product': {'id': 'gid://shopify/Product/11'}}
                for i in range(page_size)
            ]},
        )

        first_page = {'data': {'inventoryItem': {'variants': {
            'nodes': [{'id': 'gid://shopify/ProductVariant/100', 'product': {'id': 'gid://shopify/Product/11'}}],
            'pageInfo': {'endCursor': 'cursor1', 'hasNextPage': True},
        }}}}
        second_page = {'data': {'inventoryItem': {'variants': {
            'nodes': [{'id': 'gid://shopify/ProductVariant/200', 'product': {'id': 'gid://shopify/Product/11'}}],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}}

        with patch.object(InventoryItem, 'execute', side_effect=[first_page, second_page]) as execute_mock:
            variants = item.get_variants()

        self.assertEqual(execute_mock.call_count, 2)
        self.assertIsNone(execute_mock.call_args_list[0].kwargs['variables']['cursor'])
        self.assertEqual(execute_mock.call_args_list[1].kwargs['variables']['cursor'], 'cursor1')
        self.assertEqual([v.external_id for v in variants], ['11-100', '11-200'])

    def test_repeated_calls_after_a_follow_up_do_not_refetch(self):
        page_size = GraphQLTemplate.INVENTORY_ITEM_VARIANTS_PAGE_SIZE
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/7',
            variants={'nodes': [
                {'id': f'gid://shopify/ProductVariant/{i}', 'product': {'id': 'gid://shopify/Product/11'}}
                for i in range(page_size)
            ]},
        )

        follow_up = {'data': {'inventoryItem': {'variants': {
            'nodes': [{'id': 'gid://shopify/ProductVariant/100', 'product': {'id': 'gid://shopify/Product/11'}}],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}}

        with patch.object(InventoryItem, 'execute', return_value=follow_up) as execute_mock:
            first_call = item.get_variants()
            second_call = item.get_variants()

        execute_mock.assert_called_once()
        self.assertEqual([v.external_id for v in first_call], ['11-100'])
        self.assertEqual([v.external_id for v in second_call], ['11-100'])

    def test_repeated_calls_when_true_total_equals_page_size_do_not_refetch(self):
        """The follow-up query can itself return exactly PAGE_SIZE nodes when that

        happens to be the real total. len(...) == PAGE_SIZE alone would then look
        "possibly truncated" forever; the cached-fetch flag must stop that.
        """
        page_size = GraphQLTemplate.INVENTORY_ITEM_VARIANTS_PAGE_SIZE
        item = self._gql().InventoryItem.set(
            id='gid://shopify/InventoryItem/8',
            variants={'nodes': [
                {'id': f'gid://shopify/ProductVariant/{i}', 'product': {'id': 'gid://shopify/Product/11'}}
                for i in range(page_size)
            ]},
        )

        follow_up_exactly_page_size = {'data': {'inventoryItem': {'variants': {
            'nodes': [
                {'id': f'gid://shopify/ProductVariant/{100 + i}', 'product': {'id': 'gid://shopify/Product/11'}}
                for i in range(page_size)
            ],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}}

        with patch.object(InventoryItem, 'execute', return_value=follow_up_exactly_page_size) as execute_mock:
            first_call = item.get_variants()
            second_call = item.get_variants()

        execute_mock.assert_called_once()
        self.assertEqual(len(first_call), page_size)
        self.assertEqual([v.external_id for v in first_call], [v.external_id for v in second_call])
