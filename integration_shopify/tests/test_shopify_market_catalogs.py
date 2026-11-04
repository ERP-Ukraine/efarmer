# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL


MARKET_GID = 'gid://shopify/Market/10'


@tagged('post_install', '-at_install')
class TestShopifyMarketCatalogs(TransactionCase):
    """Market catalogs are read without market regions nested in the catalog query.

    Shopify bills a query by the page sizes it requests, so catalogs x markets x regions in one
    query exceeds the single-query cost limit even on a store with a single catalog.
    """

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def _catalog_node(self):
        return {
            'id': 'gid://shopify/MarketCatalog/1',
            'title': 'Europe catalog',
            'status': 'ACTIVE',
            'priceList': {
                'id': 'gid://shopify/PriceList/5',
                'name': 'Europe prices',
                'currency': 'EUR',
                'parent': None,
            },
            'publication': {
                'id': 'gid://shopify/Publication/7',
            },
            'markets': {
                'nodes': [{
                    'id': MARKET_GID,
                    'name': 'Europe',
                    'type': 'REGION',
                    'currencySettings': {
                        'baseCurrency': {
                            'currencyCode': 'EUR',
                            'currencyName': 'Euro',
                            'enabled': True,
                        },
                    },
                }],
            },
        }

    def _fetch(self):
        queries = []

        def execute(client, query, *args, **kwargs):
            queries.append(query)
            return {'data': {'catalogs': {'nodes': [self._catalog_node()]}}}

        gql = self._gql()
        with patch.object(type(gql), 'execute', autospec=True, side_effect=execute):
            catalogs = gql.MarketCatalog.fetch_all()

        return catalogs, queries

    def test_catalog_query_does_not_request_market_regions(self):
        __, queries = self._fetch()

        self.assertEqual(len(queries), 1)
        self.assertNotIn('regionsCondition', queries[0])
        self.assertIn('currencySettings', queries[0])

    def test_market_data_is_built_from_catalog_query(self):
        catalogs, __ = self._fetch()

        self.assertEqual(catalogs[0].to_odoo_format()['market_data'], {
            'markets': [{
                'id': MARKET_GID,
                'name': 'Europe',
                'type': 'REGION',
                'currency_code': 'EUR',
                'currency_name': 'Euro',
                'regions': [],
            }],
        })
