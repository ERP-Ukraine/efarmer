# See LICENSE file for full copyright and licensing details.

from datetime import datetime

from .init_integration_shopify import IntegrationShopifyBase
from ..shopify.connection import GraphQLClient


class TestShopifyReceiveOrdersPagination(IntegrationShopifyBase):
    """Shopify cursor pagination: more pages -> endCursor token, last page -> None,
    and a page_token becomes the `after:` cursor of the next query."""

    def setUp(self):
        super().setUp()
        self.integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

    def _order(self, oid, updated):
        return {
            'id': 'gid://shopify/Order/%s' % oid,
            'updatedAt': updated,
            'createdAt': updated,
        }

    def _patch_orders_query(self, has_next_page, end_cursor, orders):
        """Stub the GraphQL response for the orders query and record the sent query."""
        calls = {}

        def _execute(client_self, query, variables=None, user_errors_path='', **kw):
            calls['query'] = query
            return {'data': {'orders': {
                'pageInfo': {'hasNextPage': has_next_page, 'endCursor': end_cursor},
                'edges': [{'node': order} for order in orders],
            }}}

        self.patch(GraphQLClient, 'execute', _execute)
        return calls

    def test_more_pages_returns_end_cursor(self):
        self._patch_orders_query(True, 'CURSOR-2', [self._order(1, '2026-06-22T05:20:00Z')])

        result, next_page_token = self.adapter.receive_orders()

        self.assertEqual(len(result), 1)
        self.assertEqual(next_page_token, 'CURSOR-2')

    def test_last_page_returns_no_token(self):
        self._patch_orders_query(False, 'CURSOR-END', [self._order(1, '2026-06-22T05:20:00Z')])

        result, next_page_token = self.adapter.receive_orders()

        self.assertIsNone(next_page_token)

    def test_continuation_uses_after_cursor(self):
        calls = self._patch_orders_query(False, '', [])

        self.adapter.receive_orders(page_token='CURSOR-1')

        self.assertIn('after: "CURSOR-1"', calls['query'])
