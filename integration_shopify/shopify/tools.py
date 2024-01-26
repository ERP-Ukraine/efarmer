#  See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import ValidationError

from time import sleep
import logging

_logger = logging.getLogger(__name__)

try:
    from pyactiveresource.connection import ClientError  # HTTP error 4xx (401..499)
    from pyactiveresource.connection import ResourceNotFound  # HTTP error 404
except (ImportError, IOError) as ex:
    _logger.error(ex)

LIMIT = 10
TIMEOUT = 4
RESOURCE_NOT_FOUND = 404
TOO_MANY_REQUESTS = 429


class check_scope:
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


def _process_request(method, *args, attempt=int(), **kwargs):
    try:
        result = method(*args, **kwargs)
    except ResourceNotFound as ex:
        result = False
        _logger.warning('HTTP %s: shopify external resource not found.', ex.code)
        _logger.error(ex)
    except ClientError as ex:
        if ex.code == TOO_MANY_REQUESTS and attempt < LIMIT:
            method_info = f'{method.__name__}; {args}; {kwargs}'
            _logger.info(f'HTTP 429: shopify query, attempt {attempt + 1}: {method_info}')
            _logger.error(ex)
            sleep(TIMEOUT)
            return _process_request(method, *args, attempt=attempt + 1, **kwargs)
        else:
            raise ex

    return result


def catch_exception(method):
    def _catch_exception(*args, **kwargs):
        return _process_request(method, *args, **kwargs)
    return _catch_exception
