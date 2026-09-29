# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL
from odoo.addons.integration_shopify.shopify.resources.collection import Collection


@tagged('post_install', '-at_install')
class TestShopifyCollectionCreate(TransactionCase):
    """collectionCreate must use CollectionCreateInput (the 2026-07 argument)."""

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def test_create_sends_collection_argument_not_legacy_input(self):
        payload = {
            'data': {
                'collectionCreate': {
                    'collection': {
                        'id': 'gid://shopify/Collection/1',
                        'title': 'Hats',
                    },
                    'userErrors': [],
                },
            },
        }

        with patch.object(Collection, 'execute', return_value=payload) as mocked:
            created = self._gql().Collection.create('Hats')

        mocked.assert_called_once()
        query = mocked.call_args[0][0]
        variables = mocked.call_args.kwargs['variables']

        self.assertIn('$collection: CollectionCreateInput!', query)
        self.assertIn('collectionCreate(collection: $collection)', query)
        self.assertNotIn('CollectionInput', query)
        self.assertEqual(variables, {'collection': {'title': 'Hats'}})
        self.assertEqual(created.title, 'Hats')
        self.assertEqual(created.id_str, '1')
