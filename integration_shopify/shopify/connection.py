# See LICENSE file for full copyright and licensing details.

import logging

import requests

from odoo.addons.integration.tools import ExtractNode, catch_exception
from odoo.addons.integration.exceptions import ErrorStore as es

from .exceptions import ShopifyApiError
from ..tools import loggify_request_payload, prepare_shopify_url


_logger = logging.getLogger(__name__)

_SHOPIFY_BATCH_LIMIT = 250

"""
http.client.RemoteDisconnected
    ↓
urllib3.exceptions.ProtocolError
    ↓
requests.exceptions.ConnectionError
"""


class GraphQLClient:

    _instance = {}
    _request_limit = _SHOPIFY_BATCH_LIMIT

    def __new__(cls, *args):
        instance = cls._instance.get(args)

        if not isinstance(instance, cls):
            instance = object.__new__(cls)
            cls._instance[args] = instance

        return instance

    def __init__(self, url: str, token: str, version: str, debug: bool):
        self.url = prepare_shopify_url(url)
        self.token = token.strip()
        self.version = version.strip()
        self._debug = debug

        self.headers = {
            'Accept-Language': 'en',  # Receive API messages in English
            'Accept': 'application/json',
            'X-Shopify-Access-Token': self.token,
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-Integration-Shopify/1.0',
        }

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

        # Handle shopify graphql errors. It's possible even if the response status-code is 200
        self._handle_graphql_errors(data)

        # Hande shopify user errors
        if user_errors_path:
            error = ExtractNode.extract_raw(data, user_errors_path, list)
            if error:
                raise ShopifyApiError(str(error))

        return data

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
