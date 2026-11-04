#  See LICENSE file for full copyright and licensing details.

import logging
from functools import wraps

from psycopg2 import Error
from werkzeug.wrappers import Response

from odoo import SUPERUSER_ID
from odoo.api import Environment
from odoo.http import request, db_list
from odoo.modules.registry import Registry


_logger = logging.getLogger(__name__)

# Only a 2xx tells the store the event was consumed; anything else gets it retried and, after repeated
# failures, the subscription deleted or disabled. States Odoo is in on purpose therefore answer 2xx.
WEBHOOK_OK = 200
WEBHOOK_SKIPPED = 200
WEBHOOK_BAD_REQUEST = 400
WEBHOOK_UNAUTHORIZED = 401
WEBHOOK_UNAVAILABLE = 503


def webhook_response(message, status=WEBHOOK_OK):
    """
    Build the plain-text reply for a webhook request.
    """
    return Response(message, status=status, content_type='text/plain; charset=utf-8')


def _unpack_verification(result):
    """
    Unpack the result of `IntegrationWebhook.verify_webhook()`.

    Overrides may still return the old `(is_verified, message)`; their failures answer 400.
    """
    if len(result) == 3:
        return result

    is_verified, message = result
    return is_verified, message, WEBHOOK_OK if is_verified else WEBHOOK_BAD_REQUEST


def build_environment(func):
    """
    Build environment from the webhook request.
    """
    @wraps(func)
    def wrapper(*args, **kw):
        db = kw.get('dbname')
        if not db:
            message = 'Database name is missing.'
            _logger.error(message)
            return webhook_response(message, WEBHOOK_BAD_REQUEST)

        kw['dbname'] = db
        if db not in db_list(force=True):
            message = f'Database "{db}" not found!'
            _logger.error(message)
            return webhook_response(message, WEBHOOK_BAD_REQUEST)

        if not request.env or request.db != db:
            try:
                registry = Registry(db).check_signaling()
            except Error as ex:
                # Database-level failures are transient, ask for a retry.
                _logger.error('Cannot reach the registry of database "%s": %s', db, ex.args[0])
                return webhook_response(ex.args[0], WEBHOOK_UNAVAILABLE)

            with registry.cursor() as cr:
                env = Environment(cr, SUPERUSER_ID, {})
                request.env = env
                return func(*args, **kw)

        request.update_env(user=SUPERUSER_ID)
        return func(*args, **kw)

    return wrapper


def validate_integration(func):
    """
    Validate integration according to webhook request.
    """
    @wraps(func)
    def wrapper(self, *args, **kw):
        """
        :self: an instance of the IntegrationWebhook class
        """
        integration_id = kw.get('integration_id')
        integration = request.env['sale.integration'].browse(integration_id).exists()
        integration = integration.filtered(lambda x: x.type_api == self.integration_type)

        if not integration:
            message = 'Webhook unrecognized integration.'
            _logger.error(message)
            return webhook_response(message, WEBHOOK_BAD_REQUEST)

        if not integration.is_active:
            message = f'{integration.name}: Integration is inactive.'
            request.env['integration.logging'].write_log(
                integration, 'webhook', 'Webhook Validation Failed', message,
                log_level='error',
            )
            # A deliberate state: answer 2xx so the store keeps the subscription.
            return webhook_response(message, WEBHOOK_SKIPPED)

        is_verified, message, status = _unpack_verification(self.verify_webhook(integration))
        if not is_verified:
            request.env['integration.logging'].write_log(
                integration, 'webhook', 'Webhook Verification Failed', message,
                log_level='error',
            )
            return webhook_response(message, status)

        event_name, log_message = self._prepare_webhook_log_data(*args, **kw)
        request.env['integration.logging'].write_log(
            integration, 'webhook', event_name, log_message,
            log_level='info',
        )

        return func(self, *args, **kw)

    return wrapper


def with_webhook_context(method):
    """
    Decorator to add webhook context to methods.
    """
    @wraps(method)
    def wrapper(self, integration, external_id, *args, **kwargs):
        _logger.info(f'Applying webhook context to {method.__name__} for {integration.name}')

        ctx = dict(request.env.context)
        ctx['integration_event_source'] = 'webhook action'

        integration = integration.with_context(ctx)
        return method(self, integration, external_id, *args, **kwargs)

    return wrapper
