#  See LICENSE file for full copyright and licensing details.

import json
import logging

from psycopg2 import Error
from werkzeug.exceptions import NotFound

from odoo import api, registry, SUPERUSER_ID, _
from odoo.http import request
from odoo.exceptions import ValidationError

from ..models.sale_integration import LOG_SEPARATOR


_logger = logging.getLogger(__name__)


class IntegrationWebhook:

    SHOP_NAME = ''
    TOPIC_NAME = ''
    NEW_ORDER_METHOD_NAME = ''

    @property
    def integration_type(self):
        return None

    def get_webhook_topic(self):
        headers = self._get_headers()
        return headers.get(self.TOPIC_NAME, False)

    def check_essential_headers(self):
        headers = self._get_headers()
        essential_headers = self._get_essential_headers()
        return all(headers.get(x) for x in essential_headers)

    def get_shop_domain(self, integration):
        headers = self._get_headers()
        return headers.get(self.SHOP_NAME, False)

    def verify_webhook(self, integration):
        name = integration.name
        # 1. Verify integration activation
        if not integration.is_active:
            return False, '%s integration is inactive.' % name

        # 2. Verify headers
        headers_ok = self.check_essential_headers()
        if not headers_ok:
            return False, '%s webhook invalid headers.' % name

        # 3. Verify forwarded host
        shop_domain = self.get_shop_domain(integration)
        settings_url = integration._truncate_settings_url()
        if settings_url not in shop_domain:
            return False, '%s webhook invalid shop domain "%s".' % (name, shop_domain)

        # 4. Verify integration webhook-lines
        if not integration.webhook_line_ids:
            return False, '%s webhooks not specified.' % name

        # 5. Verify webhook-line activation
        topic = self.get_webhook_topic()
        webhook_line_id = integration.webhook_line_ids\
            .filtered(lambda x: x.technical_name == topic)
        if not webhook_line_id.is_active:
            return False, 'Disabled %s webhook in Odoo "%s".' % (name, topic)

        # 6. Verify webhook digital sign
        sign_ok = self._check_webhook_digital_sign(integration)
        if not sign_ok:
            return False, 'Wrong %s webhook digital signature.' % name

        return True, '%s: webhook has been verified.' % name

    def _get_headers(self):
        return request.httprequest.headers

    def _get_post_data(self):
        return json.loads(request.httprequest.data)

    def _check_webhook_digital_sign(self, integration):
        raise NotImplementedError

    def _get_hook_name_method(self):
        headers = self._get_headers()
        return headers[self.TOPIC_NAME]

    def _get_essential_headers(self):
        raise NotImplementedError

    def _prepare_pipeline_data(self):
        raise NotImplementedError

    def _prepare_log_vals(self, integration, *args, **kw):
        message_dict = {
            'ARGS: ': args,
            'KWARGS: ': kw,
            'HEADERS: ': dict(self._get_headers()),
            'POST-DATA: ': self._get_post_data(),
        }
        message_data = json.dumps(message_dict, indent=4)
        method_name = self._get_hook_name_method()
        vals = {
            'name': f'{self.integration_type}: {method_name}',
            'type': 'client',
            'level': 'DEBUG',
            'dbname': request.env.cr.dbname,
            'message': message_data,
            'path': self.__module__,
            'func': self.__class__.__name__,
            'line': str(integration),
        }
        return vals

    def _create_log(self, integration, *args, **kw):
        vals = self._prepare_log_vals(integration, *args, **kw)
        self._print_debug_data(vals)
        return self._save_log(vals)

    def _save_log(self, vals):
        try:
            db_registry = registry(request.env.cr.dbname)
            with db_registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, SUPERUSER_ID, {})
                log = new_env['ir.logging'].create(vals)
        except Error:
            log = request.env['ir.logging']

        return log

    def _print_debug_data(self, message_data):
        _logger.info(LOG_SEPARATOR)
        _logger.info('%s WEBHOOK DEBUG', self.integration_type)
        _logger.info(message_data)
        _logger.info(LOG_SEPARATOR)

    def _is_new_order(self):
        """
        Compare current event type with new order event type to check if
        this is a new order was received
        """
        method_name_from_header = self._get_hook_name_method()
        return method_name_from_header == self.NEW_ORDER_METHOD_NAME

    def _run_method_from_header(self, *args, **kw):
        name_method = self._get_hook_name_method()
        if not hasattr(self, name_method):
            _logger.info('Hook method "%s" for %s not found!', name_method, self.integration_type)
            return False
        return getattr(self, name_method)(*args, **kw)

    def _get_order_sub_status_tuple(self, integration, status_code):
        _name = 'sale.order.sub.status'
        sub_status_id = request.env[_name]\
            .from_external(integration, status_code, raise_error=False)

        external_sub_status = request.env[f'integration.{_name}.external']\
            .get_external_by_code(integration, status_code, raise_error=False)

        if not sub_status_id:
            _logger.error(
                f'{integration.name}: Sales Order sub-status not found '
                f'(status_code={status_code})'
            )

        return sub_status_id, external_sub_status

    def _receive_order_generic(self, integration):
        external_order_id = self._get_value_from_post_data('id')
        if self._is_new_order():
            return self._run_method_from_header(integration, external_order_id)
        return self._receive_generic(integration, external_order_id)

    def _receive_generic(self, integration, external_order_id):
        input_file = request.env['sale.integration.input.file'].search([
            ('si_id', '=', integration.id),
            ('name', '=', str(external_order_id)),
        ], limit=1)

        if not input_file:
            message = (
                f'{integration.name}: Integration Input-file not found '
                f'(external_id={external_order_id})'
            )
            _logger.warning(message)
            return NotFound(message)

        if not input_file.order_id:
            input_file.mark_for_update()

            if integration.save_webhook_log:
                vals = input_file._prepare_log_vals()
                self._save_log(vals)

            message = (
                f'{integration.name}: Odoo Sales Order not found '
                f'(external_id={external_order_id})'
            )
            _logger.warning(message)
            return NotFound(message)

        return self._run_method_from_header(input_file)

    def _get_value_from_post_data(self, key):
        post_data = self._get_post_data()

        if key in post_data:
            return post_data.get(key)

        raise ValidationError(
            _('%s: "%s" not found in the post data') % (self.integration_type, key)
        )
