#  See LICENSE file for full copyright and licensing details.

import hmac
import base64
from hashlib import sha256
import logging
from werkzeug.wrappers import Response

from odoo.http import Controller, route, request
from odoo.addons.integration.controllers.integration_webhook import IntegrationWebhook
from odoo.addons.integration.controllers.utils import build_environment, validate_integration, with_webhook_context

from ..shopify_api import SHOPIFY


_logger = logging.getLogger(__name__)


class ShopifyWebhook(Controller, IntegrationWebhook):

    _kwargs = {
        'type': 'json',
        'auth': 'none',
        'methods': ['POST'],
        'csrf': False,
    }

    """
    headers = {
        X-Forwarded-Host: ventor-dev-integration-webhooks-test-15-main-5524588.dev.odoo.com
        X-Forwarded-For: 34.133.113.228
        X-Forwarded-Proto: https
        X-Real-Ip: 34.133.113.228
        Connection: close
        Content-Length: 1757
        User-Agent: Shopify-Captain-Hook
        Accept: */*
        Accept-Encoding: gzip;q=1.0,deflate;q=0.6,identity;q=0.3
        Content-Type: application/json
        X-Shopify-Api-Version: 2022-04
        X-Shopify-Hmac-Sha256: jgX3NMnUpTwfDuFXr0ufE//LiH1K+IGwd26+hy0wVik=
        X-Shopify-Product-Id: 8060197470448
        X-Shopify-Shop-Domain: vendevstore.myshopify.com
        X-Shopify-Topic: orders/paid
        X-Shopify-Webhook-Id: e62018d6-92e0-43a3-a96c-f74404f5bd15
    }
    """

    SHOP_NAME = 'X-Shopify-Shop-Domain'
    TOPIC_NAME = 'X-Shopify-Topic'

    @property
    def integration_type(self):
        return SHOPIFY

    def get_webhook_topic(self):
        topic = super(ShopifyWebhook, self).get_webhook_topic()

        if not topic:
            return topic

        return '_'.join(topic.split('/')).upper()

    def _check_webhook_digital_sign(self, integration):
        """
        Verify that the incoming webhook request is genuinely from Shopify.

        Shopify signs webhooks using HMAC-SHA256 with the app's client secret.
        Note: After secret rotation, Shopify uses the oldest unrevoked secret
        and may take up to 1 hour to switch to a new secret.

        Reference: https://shopify.dev/docs/apps/build/webhooks/subscribe/https#verify-a-webhook
        """
        # Check if validation is enabled
        if not integration.enable_webhook_hmac_validation:
            _logger.warning(
                'Shopify webhook HMAC validation is DISABLED for integration %s. '
                'This should only be temporary during secret rotation.',
                integration.id
            )
            return True

        headers = self._get_headers()
        hmac_header = headers.get('X-Shopify-Hmac-Sha256')

        if not hmac_header:
            _logger.warning(
                'Shopify webhook missing X-Shopify-Hmac-Sha256 header. '
                'This may indicate the request is not from Shopify.'
            )
            return False

        # Get the raw request body (as bytes) - this is what Shopify signs
        raw_body = request.httprequest.data
        if not raw_body:
            _logger.warning('Shopify webhook has empty request body')
            return False

        api_secret_key = integration.get_settings_value('secret_key')
        if not api_secret_key:
            _logger.error(
                'Shopify integration %s is missing secret_key configuration',
                integration.id
            )
            return False

        # Compute HMAC-SHA256 using the secret key and raw body
        # Shopify uses the raw bytes of the request body for signing
        try:
            digest = hmac.new(
                api_secret_key.encode('utf-8'),
                raw_body,
                digestmod=sha256
            ).digest()
            computed_hmac = base64.b64encode(digest).decode('utf-8')
        except Exception as e:
            _logger.exception('Error computing HMAC for webhook verification: %s', e)
            return False

        # Use timing-safe comparison to prevent timing attacks
        is_valid = hmac.compare_digest(computed_hmac, hmac_header)

        if is_valid:
            _logger.debug('Shopify webhook HMAC validation successful')
        else:
            _logger.warning(
                'Shopify webhook HMAC validation FAILED. '
                'If you recently rotated your secret key, note that Shopify may take '
                'up to 1 hour to start using the new secret. '
                'Expected HMAC: %s..., Received HMAC: %s...',
                computed_hmac[:20] if computed_hmac else 'None',
                hmac_header[:20] if hmac_header else 'None'
            )

        return is_valid

    def _get_hook_name_method(self):
        headers = self._get_headers()
        topic = headers[self.TOPIC_NAME]
        return '_'.join(topic.split('/'))

    def _get_essential_headers(self):
        return [
            self.SHOP_NAME,
            self.TOPIC_NAME,
            'X-Shopify-Hmac-Sha256',
        ]

    def _get_events_mapping(self):
        return {
            'ORDERS_CREATE': '_process_create_order',
            'ORDERS_PAID': '_process_pay_order',
            'ORDERS_PARTIALLY_FULFILLED': '_process_partially_fulfill_order',
            'ORDERS_FULFILLED': '_process_fulfill_order',
            'ORDERS_CANCELLED': '_process_cancel_order',
            'PRODUCTS_CREATE': '_process_create_product',
            'PRODUCTS_UPDATE': '_process_update_product',
            'PRODUCTS_DELETE': '_process_delete_product',
        }

    # Handle orders
    @route(f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/orders', **_kwargs)
    @build_environment
    @validate_integration
    def shopify_receive_orders(self, *args, **kw):
        """
        Expected methods:
            ORDERS_CREATE
            ORDERS_PAID
            ORDERS_CANCELLED
            ORDERS_FULFILLED
            ORDERS_PARTIALLY_FULFILLED
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_orders()')
        integration = request.env['sale.integration'].browse(kw['integration_id'])
        external_order_id = self._get_value_from_post_data('id')
        return self._process_event(integration, external_order_id)

    def _prepare_pipeline_data(self, integration, external_order_id):
        order = integration.adapter.gql.Order.get_by_pk(external_order_id)  # FIXME: not a good idea

        vals = {
            'external_tags': order.tags,
            'payment_method': order.parse_payment_method(),
            'integration_workflow_states': order.parse_workflow_states(),
            'order_fulfillments': order.parse_fulfillments(),
            'date_order': order.created_at,
        }

        return vals

    @with_webhook_context
    def _process_cancel_order(self, integration, external_order_id):
        _logger.info(f'Call {integration.name} webhook controller: _process_cancel_order')
        data = self._prepare_pipeline_data(integration, external_order_id)

        # Handle order existence check
        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        # Order exists, proceed with cancel logic
        integration.cancel_order_by_id_with_delay(external_order_id, data)
        return Response(f'Job created for order with code={external_order_id}. Action: cancel order')

    @with_webhook_context
    def _process_pay_order(self, integration, external_order_id):
        _logger.info(f'Call {integration.name} webhook controller method: _process_pay_order')
        data = self._prepare_pipeline_data(integration, external_order_id)

        # Handle order existence check
        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        # Order exists, proceed with pay order processing
        integration.process_pipeline_by_id_with_delay(external_order_id, data, build_and_run=True)
        return Response(f'Job created for order with code={external_order_id}. Action: process pay order')

    @with_webhook_context
    def _process_fulfill_order(self, integration, external_order_id):
        _logger.info(f'Call {integration.name} webhook controller method: _process_fulfill_order')
        data = self._prepare_pipeline_data(integration, external_order_id)

        # Handle order existence check
        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        # Order exists, proceed with fulfill order processing
        integration.process_pipeline_by_id_with_delay(external_order_id, data, build_and_run=True)
        return Response(f'Job created for order with code={external_order_id}. Action: process fulfill order')

    @with_webhook_context
    def _process_partially_fulfill_order(self, integration, external_order_id):
        _logger.info(f'Call {integration.name} webhook controller method: _process_partially_fulfill_order')
        data = self._prepare_pipeline_data(integration, external_order_id)

        # Handle order existence check
        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        # Order exists, proceed with partially fulfill order processing
        integration.process_pipeline_by_id_with_delay(external_order_id, data, build_and_run=True)
        return Response(f'Job created for order with code={external_order_id}. Action: process partially fulfill order')

    # Handle products
    @route(f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/products', **_kwargs)
    @build_environment
    @validate_integration
    def shopify_receive_products(self, *args, **kw):
        """
        Expected methods:
            PRODUCTS_CREATE
            PRODUCTS_UPDATE
            PRODUCTS_DELETE
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_products()')

        integration = request.env['sale.integration'].browse(kw['integration_id'])
        external_product_id = self._get_value_from_post_data('id')

        return self._process_event(integration, external_product_id)

    def _get_product_name(self, integration):
        return self._get_value_from_post_data('title')
