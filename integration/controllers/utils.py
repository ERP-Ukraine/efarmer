#  See LICENSE file for full copyright and licensing details.

from functools import wraps

from odoo import SUPERUSER_ID
from odoo.http import request, db_list
from werkzeug.exceptions import BadRequest

from uuid import uuid1
import logging


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

        request_db = request.db
        if not request_db or request_db != db:
            request.httprequest.session.db = db
            request.httprequest.session.uid = SUPERUSER_ID
            request.httprequest.session.session_token = str(uuid1())
            return func(*args, **kw)

        request.env.uid = SUPERUSER_ID
        return func(*args, **kw)

    return wrapper


def validate_integration(func):
    """
    Validate integration according to webhook request.
    """
    @wraps(func)
    def wrapper(self, *args, **kw):
        integration_id = kw.get('integration_id')
        integration = request.env['sale.integration'].browse(integration_id).exists()
        integration = integration.filtered(lambda x: x.type_api == self.integration_type)

        if not integration:
            message = 'Webhook unrecognized integration.'
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
            self._create_log(integration, *args, **kw)

        return func(self, *args, **kw)

    return wrapper
