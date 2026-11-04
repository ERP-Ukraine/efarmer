# See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions, GraphQLClient


COST_HEADER = 'Shopify-GraphQL-Cost-Debug'
LOGGER = 'odoo.addons.integration_shopify.shopify.connection'

COST = {
    'requestedQueryCost': 453,
    'actualQueryCost': 4,
    'throttleStatus': {'maximumAvailable': 2000.0, 'currentlyAvailable': 1996, 'restoreRate': 100.0},
    'fields': [
        {'path': ['catalogs', 'nodes', 'title'], 'definedCost': 0, 'requestedTotalCost': 0},
        {'path': ['catalogs', 'nodes', 'markets'], 'definedCost': 0, 'requestedTotalCost': 35},
        {'path': ['catalogs'], 'definedCost': 2, 'requestedTotalCost': 453},
    ],
}


@tagged('post_install', '-at_install')
class TestShopifyQueryCostDebug(TransactionCase):
    """The undocumented cost debug header follows debug_mode and backs the shell diagnostic."""

    def _client(self, debug):
        return GraphQLClient('shopifytestsite.myshopify.com', 'shpat_test', '2026-07', debug, ClientOptions())

    def _response(self, data):
        response = MagicMock()
        response.json.return_value = data
        return response

    def test_header_follows_debug_mode(self):
        self.assertEqual(self._client(True).headers.get(COST_HEADER), '1')
        self.assertNotIn(COST_HEADER, self._client(False).headers)

    def test_debug_execute_logs_most_expensive_fields(self):
        client = self._client(True)
        response = self._response({'data': {'catalogs': {'nodes': []}}, 'extensions': {'cost': COST}})

        # The module logger is replaced rather than captured with assertLogs: whether an INFO record
        # reaches a handler depends on the test runner's logging setup, which differs between versions.
        with patch(f'{LOGGER}.requests.post', return_value=response), patch(f'{LOGGER}._logger') as logger:
            client.execute('{ catalogs(first: 250) { nodes { title } } }')

        cost_lines = [x.args[0] % x.args[1:] for x in logger.info.call_args_list if 'GQL-COST' in x.args[0]]
        self.assertEqual(len(cost_lines), 1)
        self.assertIn('requested 453, actual 4', cost_lines[0])
        self.assertIn('catalogs=453, catalogs.nodes.markets=35', cost_lines[0])
        self.assertNotIn('title', cost_lines[0])

    def test_get_query_cost_sends_header_without_debug_mode(self):
        client = self._client(False)
        response = self._response({'data': {}, 'extensions': {'cost': COST}})

        with patch(f'{LOGGER}.requests.post', return_value=response) as post:
            cost = client.get_query_cost('{ catalogs(first: 250) { nodes { title } } }')

        self.assertEqual(cost, COST)
        self.assertEqual(post.call_args.kwargs['headers'][COST_HEADER], '1')
        self.assertNotIn(COST_HEADER, client.headers)

    def test_get_query_cost_returns_max_cost_exceeded_extensions(self):
        client = self._client(False)
        extensions = {'code': 'MAX_COST_EXCEEDED', 'cost': 1366, 'maxCost': 1000}
        response = self._response({'errors': [{'message': 'Query cost is 1366', 'extensions': extensions}]})

        with patch(f'{LOGGER}.requests.post', return_value=response):
            cost = client.get_query_cost('{ catalogs(first: 250) { nodes { title } } }')

        self.assertEqual(cost, extensions)
