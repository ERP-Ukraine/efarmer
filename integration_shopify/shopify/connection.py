# See LICENSE file for full copyright and licensing details.

import logging

import requests
from requests.exceptions import HTTPError

from odoo.addons.integration.tools import ExtractNode, catch_exception
from odoo.addons.integration.exceptions import ErrorStore as es

from .exceptions import ShopifyApiError
from ..tools import loggify_request_payload, prepare_shopify_url


_logger = logging.getLogger(__name__)


RESOURCE_CONFLICT = 409
TOO_MANY_REQUESTS = 429

INTERNAL_SERVER_ERROR = 500
BAD_GATEWAY = 502
SERVICE_UNAVAILABLE = 503
CONNECTION_TIMED_OUT = 522
TIMEOUT_OCCURRED = 524
UNABLE_RESOLVE_ORIGIN_HOSTNAME = 530

SERVER_ERROR_CODES = [
    INTERNAL_SERVER_ERROR, BAD_GATEWAY, SERVICE_UNAVAILABLE,
    CONNECTION_TIMED_OUT, TIMEOUT_OCCURRED, UNABLE_RESOLVE_ORIGIN_HOSTNAME,
]

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
        if 'errors' in data:
            raise ShopifyApiError(str(data['errors']))

        # Check shopify user errors
        if user_errors_path:
            error = ExtractNode.extract_raw(data, user_errors_path, list)
            if error:
                raise ShopifyApiError(str(error))

        return data

    def _handle_http_error(self, response):
        try:
            response.raise_for_status()
        except HTTPError as ex:
            message = ex.args[0] + '\n\n' + response.text
            code = response.status_code

            if code == es.ResourceConflict.CODE:
                raise es.ResourceConflict(message)

            if code == es.TooManyRequestsError.CODE:
                raise es.TooManyRequestsError(message)

            if code in SERVER_ERROR_CODES:
                raise es.ServerError(code, message)

            raise ex
