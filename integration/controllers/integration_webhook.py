#  See LICENSE file for full copyright and licensing details.

import json
import logging

from werkzeug.wrappers import Response

from odoo import _
from odoo.http import request
from odoo.exceptions import ValidationError

from .utils import with_webhook_context


_logger = logging.getLogger(__name__)


class IntegrationWebhook:

    SHOP_NAME = ''
    TOPIC_NAME = ''

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
        webhook_line_id = integration.webhook_line_ids.filtered(lambda x: x.technical_name == topic)
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
            'integration_id': integration.id,
            'event_type': 'webhook',
            'event_name': method_name,
            'message': message_data,
        }
        return vals

    def _process_event(self, integration, external_id):
        """
        Process the webhook event generically based on event mapping.
        """
        topic = self.get_webhook_topic()
        event_mapping = self._get_events_mapping()

        # Match the topic to a method
        method_name = event_mapping.get(topic)
        if not method_name:
            _logger.warning(
                'No method mapped for topic "%s" in integration "%s".',
                topic,
                integration.name,
            )
            return Response(f'No method for topic "{topic}".')

        # Check if the method exists and call it
        if not hasattr(self, method_name):
            _logger.error(
                'Mapped method "%s" for topic "%s" not found in "%s".',
                method_name,
                topic,
                self.__class__.__name__,
            )
            return Response(f'Method "{method_name}" not implemented.')

        method = getattr(self, method_name)
        return method(integration, external_id)

    def _get_value_from_post_data(self, key):
        post_data = self._get_post_data()

        if key in post_data:
            return post_data.get(key)

        raise ValidationError(
            _('%s: "%s" not found in the post data') % (self.integration_type, key)
        )

    def _get_events_mapping(self):
        """
        Return events mapping for the specific integration type.
        This should be overridden in child classes.
        """
        raise NotImplementedError('Subclasses must define _get_events_mapping')

    # Handle orders
    @with_webhook_context
    def _process_create_order(self, integration, external_order_id):
        """"
        Process create order event
        """
        _logger.info(f'Call {integration.name} webhook controller: _process_create_order')

        if not integration.is_order_import_enabled:
            message = f'Order import is disabled for integration {integration.name} or integration is not active.'
            _logger.info(message)
            return Response(message)

        data = self._prepare_pipeline_data()

        if not integration.is_importable_order_status(data['integration_workflow_states']):
            message = f'Order with code={external_order_id} is not in the expected status.'
            _logger.info(message)
            return Response(message)

        # Check cut-off date if configured
        date_order = data.get('date_order')
        if not integration.is_importable_order_date(date_order):
            message = (
                f'Order with code={external_order_id} was created before the cut-off date '
                f'({integration.orders_cut_off_datetime}). Order creation date: {date_order}.'
            )
            _logger.info(message)
            return Response(message)

        integration.fetch_order_by_id_with_delay(external_order_id)

        return Response(f'Job created for order with code={external_order_id}. Action: create order')

    @with_webhook_context
    def _process_update_status_order(self, integration, external_order_id):
        """
        Process update order status event
        """
        _logger.info(f'Call {integration.name} webhook controller: _process_update_status_order')

        if not integration.is_order_import_enabled:
            message = f'Order import is disabled for integration {integration.name} or integration is not active.'
            _logger.info(message)
            return Response(message)

        data = self._prepare_pipeline_data()
        status_codes = data['integration_workflow_states']

        # Handle order existence check
        should_import, message = integration._handle_missing_order(external_order_id, status_codes, data['date_order'])
        if should_import is not None:
            return Response(message)

        # Order exists, proceed with status update logic
        if integration.is_canceled_order_status(status_codes[0]):
            integration.cancel_order_by_id_with_delay(external_order_id, data)
            return Response(f'Job created for order with code={external_order_id}. Action: cancel order')

        integration.update_order_status_by_id_with_delay(external_order_id, data)
        return Response(f'Job created for order with code={external_order_id}. Action: update order status')

    def _get_product_name(self, integration):
        """
        Get product name from post data
        """
        raise NotImplementedError(_('%s: Method "_get_product_name" not implemented!') % integration.name)

    @with_webhook_context
    def _process_create_product(self, integration, external_product_id):
        """
        Process create product event
        """
        _logger.info(f'Call {integration.name} webhook controller: _process_create_product')

        name = self._get_product_name(integration)

        integration \
            .with_context(external_product_name=name) \
            .update_product_by_id_with_delay(external_product_id, check_hook_gap=True)
        # Right, Update it! Product creating may be invoked from update function if the product does not exist in Odoo.

        return Response(f'Job created for product with code={external_product_id}. Action: create product')

    @with_webhook_context
    def _process_update_product(self, integration, external_product_id):
        """
        Process update product event
        """
        _logger.info(f'Call {integration.name} webhook controller: _process_update_product')

        name = self._get_product_name(integration)

        integration \
            .with_context(external_product_name=name) \
            .update_product_by_id_with_delay(external_product_id, check_hook_gap=True)

        return Response(f'Job created for product with code={external_product_id}. Action: update product')

    @with_webhook_context
    def _process_delete_product(self, integration, external_product_id):
        """
        Process delete product event
        """
        _logger.info(f'Call {integration.name} webhook controller: _process_delete_product')

        integration.delete_product_by_id_with_delay(external_product_id)

        return Response(f'Job created for product with code={external_product_id}. Action: delete product')
