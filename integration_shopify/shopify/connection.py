# See LICENSE file for full copyright and licensing details.

import logging
from typing import NamedTuple

import requests

from odoo.addons.integration.tools import ExtractNode, catch_exception
from odoo.addons.integration.exceptions import ErrorStore as es

from .exceptions import ShopifyApiError
from ..tools import loggify_request_payload, prepare_shopify_url


_logger = logging.getLogger(__name__)

_SHOPIFY_BATCH_LIMIT = 250

# Not in Shopify's documentation, verified live on API 2026-07: with this header `extensions.cost`
# also carries `fields`, the requested cost of every field in the query. Undocumented, so nothing
# may depend on it; it only feeds debug logging and GraphQLClient.get_query_cost().
_COST_DEBUG_HEADER = 'Shopify-GraphQL-Cost-Debug'
_COST_LOG_FIELDS_LIMIT = 10

"""
http.client.RemoteDisconnected
    ↓
urllib3.exceptions.ProtocolError
    ↓
requests.exceptions.ConnectionError
"""


class ClientOptions(NamedTuple):
    """Integration settings the resource layer reads off the client.

    Immutable and hashable on purpose: GraphQLClient caches instances keyed on its constructor
    arguments, and one Shopify store may back several Odoo integrations (one per company, filtered
    by business entity) whose settings differ. Options that are part of the key keep those
    integrations on separate clients. Add new switches as fields with a default rather than as
    further constructor parameters.
    """

    enable_returns_refunds_sync: bool = False


class GraphQLClient:

    _instance = {}
    _request_limit = _SHOPIFY_BATCH_LIMIT

    def __new__(cls, *args):
        instance = cls._instance.get(args)

        if not isinstance(instance, cls):
            instance = object.__new__(cls)
            cls._instance[args] = instance

        return instance

    def __init__(self, url: str, token: str, version: str, debug: bool, options: ClientOptions):
        self.url = prepare_shopify_url(url)
        self.token = token.strip()
        self.version = version.strip()
        self._debug = debug
        # Resources read the options to shape the query body. Keeping them here rather than on the
        # parse-time props means the body and the parsers cannot disagree: whatever left fields out
        # of the query is what decides not to parse them.
        self.options = options

        self.headers = {
            'Accept-Language': 'en',  # Receive API messages in English
            'Accept': 'application/json',
            'X-Shopify-Access-Token': self.token,
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-Integration-Shopify/1.0',
        }

        if self._debug:
            self.headers[_COST_DEBUG_HEADER] = '1'

        self.admin_url = f'https://admin.shopify.com/store/{self.url.replace(".myshopify.com", "")}'
        self.api_point = f'https://{self.url}/admin/api/{self.version}/graphql.json'

    def __repr__(self):
        return f'{self.__class__.__name__} [{self.api_point}]'

    __str__ = __repr__

    @catch_exception
    def execute(self, query: str, variables: dict = None, user_errors_path=''):
        # Prepare payload
        payload = {'query': query}

        if variables:
            payload['variables'] = variables

        # Prepare log message
        log = loggify_request_payload(payload, limit=(None if self._debug else 100))
        _logger.info('%s GQL-REQUEST --> %s', self, log)

        # Send a POST request
        response = requests.post(self.api_point, json=payload, headers=self.headers)

        # Handle HTTP error
        self._handle_http_error(response)

        if self._debug:
            _logger.info('%s GQL-RESPONSE --> %s', self, response.text)

        # Extract response
        data = response.json()

        if self._debug:
            self._log_query_cost(data)

        # Handle shopify graphql errors. It's possible even if the response status-code is 200
        self._handle_graphql_errors(data)

        # Hande shopify user errors
        if user_errors_path:
            error = ExtractNode.extract_raw(data, user_errors_path, list)
            if error:
                raise ShopifyApiError(str(error))

        return data

    def get_query_cost(self, query: str, variables: dict = None) -> dict:
        """Run a query with the cost debug header and return its cost. A diagnostic for the shell.

        The query is executed, so never pass a mutation that is not meant to run. Shopify rejects a
        query over the single-query limit unexecuted and without the per-field breakdown; lower its
        page sizes (`first`) to see which fields make it expensive.

        :param query: GraphQL query
        :param variables: query variables
        :return: `extensions.cost` of the response, with `fields` while Shopify still honours the
            header, or the extensions of the MAX_COST_EXCEEDED error
        """
        payload = {'query': query}

        if variables:
            payload['variables'] = variables

        headers = dict(self.headers, **{_COST_DEBUG_HEADER: '1'})
        response = requests.post(self.api_point, json=payload, headers=headers)
        self._handle_http_error(response)
        data = response.json()

        cost = (data.get('extensions') or {}).get('cost')
        if cost:
            return cost

        for error in data.get('errors') or []:
            extensions = error.get('extensions') or {}
            if extensions.get('code') == 'MAX_COST_EXCEEDED':
                return extensions

        raise ShopifyApiError(str(data.get('errors') or data))

    def _log_query_cost(self, data: dict):
        cost = (data.get('extensions') or {}).get('cost')
        if not cost:
            return

        fields = sorted(
            [x for x in (cost.get('fields') or []) if x.get('requestedTotalCost')],
            key=lambda x: x['requestedTotalCost'],
            reverse=True,
        )
        expensive = ', '.join(
            '%s=%s' % ('.'.join(str(x) for x in field['path']), field['requestedTotalCost'])
            for field in fields[:_COST_LOG_FIELDS_LIMIT]
        )

        _logger.info(
            '%s GQL-COST --> requested %s, actual %s; most expensive fields: %s',
            self,
            cost.get('requestedQueryCost'),
            cost.get('actualQueryCost'),
            expensive or 'n/a',
        )

    def _handle_http_error(self, response):
        try:
            response.raise_for_status()
        except es.HTTPError as ex:
            message = ex.args[0] + '\n\n' + response.text
            code = response.status_code

            if code == es.RESOURCE_CONFLICT:
                raise es.ResourceConflict(message, response=response)

            if code == es.TOO_MANY_REQUESTS:
                raise es.TooManyRequestsError(message, response=response)

            if code in es.SERVER_ERROR_CODES:
                raise es.ServerError(code, message, response=response)

            raise ex

    def _handle_graphql_errors(self, data: dict):
        if 'errors' in data:
            if any((e.get('message') or '').lower() == 'throttled' for e in data['errors']):
                try:
                    cost = data['extensions']['cost']
                    ts = cost['throttleStatus']

                    timeout = ((cost['requestedQueryCost'] - ts['currentlyAvailable']) / ts['restoreRate']) + 1
                    info = str(cost)
                except (KeyError, ZeroDivisionError):
                    timeout = 4
                    info = ''

                raise es.ThrottledError(timeout, info)

            raise ShopifyApiError(str(data['errors']))
