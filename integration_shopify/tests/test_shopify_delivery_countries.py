# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL
from odoo.addons.integration_shopify.shopify.resources.delivery_profile import DeliveryProfile
from odoo.addons.integration_shopify.shopify.resources.market import Market
from odoo.addons.integration_shopify.tests.patch.shopify_api_patch import ShopifyAPIClientPatchTest


@tagged('post_install', '-at_install')
class TestShopifyDeliveryCountries(TransactionCase):
    """Countries/states come from delivery profiles, or from markets when
    market-driven shipping is on.
    """

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def _client(self):
        return ShopifyAPIClientPatchTest({
            'enable_returns_refunds_sync': False,
        })

    def _market(self, regions):
        return self._gql().Market.set(
            id='gid://shopify/Market/1',
            name='Test market',
            type='REGION',
            conditions={
                'regionsCondition': {
                    'regions': {
                        'nodes': regions,
                    },
                },
            },
        )

    def test_market_country_region_maps_to_delivery_country(self):
        market = self._market([{
            '__typename': 'MarketRegionCountry',
            'id': 'gid://shopify/MarketRegionCountry/11',
            'name': 'Poland',
            'code': 'PL',
        }])

        countries = market.to_delivery_countries()

        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0].to_odoo_format(), {
            'id': '11',
            'name': 'Poland',
            'external_reference': 'PL',
        })
        self.assertEqual(countries[0].provinces_to_odoo_format(), [])

    def test_market_subdivision_region_maps_to_country_and_state(self):
        market = self._market([{
            '__typename': 'MarketRegionSubdivision',
            'id': 'gid://shopify/MarketRegionSubdivision/22',
            'name': 'New York',
            'code': 'NY',
            'country': {
                'code': 'US',
                'name': 'United States',
            },
        }])

        countries = market.to_delivery_countries()

        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0].to_odoo_format()['external_reference'], 'US')
        self.assertEqual(countries[0].to_odoo_format()['name'], 'United States')
        self.assertEqual(countries[0].provinces_to_odoo_format(), [{
            'id': '22',
            'name': 'New York',
            'external_reference': 'US_NY',
        }])

    def test_subdivision_only_country_id_is_stable_regardless_of_region_order(self):
        """A country with no MarketRegionCountry of its own has no country-level gid to

        borrow, so its id must come from something stable (the ISO code), not from
        whichever subdivision happens to be first in the API response -- otherwise the
        external record's key changes across imports and creates a duplicate.
        """
        subdivisions = [
            {
                '__typename': 'MarketRegionSubdivision',
                'id': 'gid://shopify/MarketRegionSubdivision/22',
                'name': 'New York',
                'code': 'NY',
                'country': {'code': 'US', 'name': 'United States'},
            },
            {
                '__typename': 'MarketRegionSubdivision',
                'id': 'gid://shopify/MarketRegionSubdivision/33',
                'name': 'Texas',
                'code': 'TX',
                'country': {'code': 'US', 'name': 'United States'},
            },
        ]

        country_id = self._market(subdivisions).to_delivery_countries()[0].to_odoo_format()['id']
        reordered_country_id = self._market(list(reversed(subdivisions))).to_delivery_countries()[0] \
            .to_odoo_format()['id']

        self.assertEqual(country_id, reordered_country_id)
        self.assertNotIn(country_id, ('22', '33'))

    def test_same_country_across_markets_merges_provinces(self):
        """The same country can be split across markets (e.g. one market scoped to

        New York, another to Texas, both under the US) -- provinces from every
        market must survive, not just the first market's.
        """
        ny_market = self._market([{
            '__typename': 'MarketRegionSubdivision',
            'id': 'gid://shopify/MarketRegionSubdivision/22',
            'name': 'New York',
            'code': 'NY',
            'country': {'code': 'US', 'name': 'United States'},
        }])
        tx_market = self._market([{
            '__typename': 'MarketRegionSubdivision',
            'id': 'gid://shopify/MarketRegionSubdivision/33',
            'name': 'Texas',
            'code': 'TX',
            'country': {'code': 'US', 'name': 'United States'},
        }])

        client = self._client()
        with patch.object(Market, 'get_batch', return_value=[ny_market, tx_market]):
            countries = client._get_delivery_countries_from_markets()

        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0].to_odoo_format()['external_reference'], 'US')
        self.assertEqual(
            sorted(p['external_reference'] for p in countries[0].provinces_to_odoo_format()),
            ['US_NY', 'US_TX'],
        )

    def test_legacy_shipping_reads_delivery_profiles(self):
        client = self._client()
        client.shop.set(features={'marketDrivenShipping': False})

        with patch.object(DeliveryProfile, 'get_batch', return_value=[]) as profiles, \
                patch.object(Market, 'get_batch', return_value=[]) as markets:
            client._get_delivery_countries()

        profiles.assert_called()
        markets.assert_not_called()

    def test_market_driven_shipping_reads_markets_not_profiles(self):
        client = self._client()
        client.shop.set(features={'marketDrivenShipping': True})

        with patch.object(DeliveryProfile, 'get_batch', return_value=[]) as profiles, \
                patch.object(Market, 'get_batch', return_value=[]) as markets:
            client._get_delivery_countries()

        markets.assert_called()
        profiles.assert_not_called()
