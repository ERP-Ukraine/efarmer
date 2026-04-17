#  See LICENSE file for full copyright and licensing details.

import logging
from functools import wraps

from psycopg2 import Error
from werkzeug.exceptions import BadRequest

from odoo import SUPERUSER_ID
from odoo.api import Environment
from odoo.http import request, db_list
from odoo.modules.registry import Registry


_logger = logging.getLogger(__name__)


def build_environment(func):
    """
    Build environment from the webhook request.
    """
    @wraps(func)
    def wrapper(*args, **kw):
        db = kw.get('dbname')
        if db not in db_list(force=True):
            message = f'Database "{db}" not found!'
            _logger.error(message)
            return BadRequest(message)

        if not request.env or request.db != db:
            try:
                registry = Registry(db).check_signaling()
            except Error as ex:
                return BadRequest(ex.args[0])

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
            return BadRequest(message)

        if not integration.is_active:
            message = f'{integration.name}: Integration is inactive.'
            _logger.error(message)
            return BadRequest(message)

        is_verified, message = self.verify_webhook(integration)
        if not is_verified:
            _logger.error(message)
            return BadRequest(message)

        _logger.info(
            'Integration webhook: %s, type-api="%s", controller-integration-type="%s". %s',
            str(integration),
            integration.type_api,
            self.integration_type,
            message,
        )
        if integration.save_webhook_log:
            vals = self._prepare_log_vals(integration, *args, **kw)
            integration._save_log(vals)

        return func(self, *args, **kw)

    return wrapper


def with_webhook_context(method):
    """
    Decorator to add webhook context to methods.
    """
    def wrapper(self, integration, external_id, *args, **kwargs):
        _logger.info(f'Applying webhook context to {method.__name__} for {integration.name}')

        ctx = dict(request.env.context)
        ctx['integration_event_source'] = 'webhook action'

        integration = integration.with_context(ctx)
        return method(self, integration, external_id, *args, **kwargs)

    return wrapper
