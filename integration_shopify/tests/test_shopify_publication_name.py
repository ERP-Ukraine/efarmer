# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL


@tagged('post_install', '-at_install')
class TestShopifyPublicationName(TransactionCase):
    """Publication.name is deprecated; the channel name comes from Channel.name."""

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def test_publication_body_does_not_select_publication_name(self):
        body = GraphQLTemplate.PUBLICATION_BODY
        fields = [line.strip() for line in body.splitlines() if line.strip()]

        self.assertEqual(fields[0], 'id')
        self.assertTrue(fields[1].startswith('channels'))
        self.assertIn('catalog {', body)

    def test_channel_name_comes_from_publication_channels(self):
        publication = self._gql().Publication.set(
            id='gid://shopify/Publication/5',
            name='Deprecated publication name',
            catalog={
                'id': 'gid://shopify/AppCatalog/9',
                'title': 'Channel Catalog 5',
            },
            channels={
                'nodes': [{
                    'id': 'gid://shopify/Channel/5',
                    'name': 'Online Store',
                }],
            },
        )

        self.assertEqual(publication.to_odoo_format(), {
            'channel_id': '5',
            'channel_name': 'Online Store',
        })

    def test_channel_name_falls_back_to_catalog_title(self):
        publication = self._gql().Publication.set(
            id='gid://shopify/Publication/6',
            catalog={'title': 'Wholesale'},
        )

        self.assertEqual(publication._compute_name(), 'Wholesale')

    def test_channel_name_falls_back_when_catalog_missing(self):
        publication = self._gql().Publication.set(
            id='gid://shopify/Publication/7',
        )

        self.assertEqual(publication._compute_name(), 'Sales Channel 7')
