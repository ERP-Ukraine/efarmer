#  See LICENSE file for full copyright and licensing details.

import json
import logging
from copy import deepcopy
from time import sleep
from typing import Dict, List, Union, Type

from odoo import _
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)

try:
    from pyactiveresource.connection import ClientError  # HTTP error 4xx (401..499)
    from pyactiveresource.connection import ResourceNotFound  # HTTP error 404
    from pyactiveresource.connection import ServerError  # HTTP error code 5xx (500..599)
except (ImportError, IOError) as ex:
    _logger.error(ex)


CLIENT_LIMIT = 8
SERVER_LIMIT = 5

CLIENT_TIMEOUT = 4
SERVER_TIMEOUT = 2

RESOURCE_NOT_FOUND = 404
TOO_MANY_REQUESTS = 429
SERVICE_UNAVAILABLE = 503


class ExtractNode:

    class MissedValue:
        pass

    def __init__(self, key_string: str, return_type):
        self.keys = key_string.split('.')
        self._type = return_type

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if isinstance(result, str):
                result = json.loads(result)

            data = self._extract(result, self.keys)

            if isinstance(data, ExtractNode.MissedValue):
                return self.get_default()

            return data

        return wrapper

    def _extract(self, data, key_list):
        """
        Recursively extract the value based on the provided key list
        """
        if not key_list:
            # No more keys to process, return the current data
            return data

        key, *remaining_keys = deepcopy(key_list)

        if isinstance(data, list):
            if key.isdigit():
                if int(key) < len(data):
                    # If the key is an integer and within the list bounds, continue extraction
                    return self._extract(data[int(key)], remaining_keys)

                _logger.warning('GraphQL parse error: Index "%s" out of range', key)
                return ExtractNode.MissedValue()

            # Handle the all lists elements
            return list(filter(
                lambda x: not isinstance(x, ExtractNode.MissedValue),
                [self._extract(x, key_list) for x in data],
            ))

        if isinstance(data, dict):
            if key in data:
                return self._extract(data[key], remaining_keys)

            _logger.warning('GraphQL parse error: Key "%s" not found', key)
            return ExtractNode.MissedValue()

        # Unknown data type (neither a list nor a dictionary)_extract
        _logger.warning('GraphQL parse error: Expected list or dict at key "%s", got %s', key, type(data).__name__)
        return ExtractNode.MissedValue()

    def get_default(self):
        return self._type() if callable(self._type) else self._type

    @classmethod
    def extract_raw(cls, json_data : Union[str, Dict, List], key_string: str, return_type: Type):
        # 1. init instance
        # 2. invoke the __call__ method
        # 3. invoke the `wrapper` function returned from the step 2
        return cls(key_string, return_type)(lambda: json_data)()


class CheckScope:
    """Check Shopify API access scope."""

    def __init__(self, *scopes):
        self.scope_list = scopes

    def __call__(self, method):
        def scope_checker(instance, *args, **kw):
            for scope in self.scope_list:
                if scope not in instance.access_scopes:
                    raise ValidationError(_(
                        'The scope "%s" is not permitted in the private app of your store. '
                        'Change it in the "Admin API" settings.' % scope
                    ))
            return method(instance, *args, **kw)
        return scope_checker


def _process_request(method, *args, _client_attempt=1, _server_attempt=1, **kwargs):
    try:
        result = method(*args, **kwargs)
    except ResourceNotFound as ex:
        result = False
        _logger.warning(
            'Integration Shopify HTTP 404: external resource not found: %s',
            f'{method.__name__}; {args}; {kwargs}'
        )
    except ClientError as ex:
        if ex.code == TOO_MANY_REQUESTS and _client_attempt <= CLIENT_LIMIT:
            _logger.warning(
                'Integration Shopify HTTP 429: client-attempt %s --> wait %s: %s',
                _client_attempt,
                CLIENT_TIMEOUT,
                f'{method.__name__}; {args}; {kwargs}',
            )
            sleep(CLIENT_TIMEOUT)

            return _process_request(
                method,
                *args,
                _client_attempt=_client_attempt + 1,
                _server_attempt=_server_attempt,
                **kwargs,
            )

        raise ex
    except ServerError as ex:
        if ex.code == SERVICE_UNAVAILABLE and _server_attempt <= SERVER_LIMIT:
            _logger.warning(
                'Integration Shopify HTTP 503: server-attempt %s --> wait %s: %s',
                _server_attempt,
                SERVER_TIMEOUT ** _server_attempt,
                f'{method.__name__}; {args}; {kwargs}',
            )
            sleep(SERVER_TIMEOUT ** _server_attempt)

            return _process_request(
                method,
                *args,
                _client_attempt=_client_attempt,
                _server_attempt=_server_attempt + 1,
                **kwargs,
            )

        raise ex

    return result


def catch_exception(method):
    def _catch_exception(*args, **kwargs):
        return _process_request(method, *args, **kwargs)
    return _catch_exception


def parse_graphql_id(graphql_id: str) -> str:
    """
    Parse the ID from a Shopify GraphQL ID.
    """
    return graphql_id.rsplit('/', 1)[-1] if graphql_id else ''


def merge_orders_data(target_orders: list, source_orders: list, merge_keys: list):
    """
    Merge order data from source orders into target orders based on specified keys.

    :param target_orders: List of Order objects to update
    :param source_orders: List of dictionaries with order data to merge into target orders
    :param merge_keys: List of keys to merge from source orders to target orders
    :return: True if any orders were updated, False otherwise
    """
    # Create a mapping from order ID to the data to be merged
    source_data_map = {str(order['id']): order for order in source_orders}

    for order in target_orders:
        order_id = str(order.id)
        source_data = source_data_map.get(order_id, False)

        if source_data:
            for key in merge_keys:
                if key in source_data:
                    new_value = source_data.get(key)
                    setattr(order, key, new_value)

    return True
