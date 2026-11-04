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
from ..tools import prepare_shopify_url
from ..shopify.exceptions import ShopifyResourceNotFoundError


_logger = logging.getLogger(__name__)


class ShopifyWebhook(Controller, IntegrationWebhook):

    _kwargs = {
        # Not `jsonrpc`: it answers every outcome, errors included, with 200, so Shopify never retries.
        'type': 'http',
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

    def _verify_shop_domain(self, integration):
        """
        Also accept the <id>.myshopify.com domain the API client builds from the stored Shop ID.

        The header always carries the full domain, while many integrations store only the short ID
        in `url`, and `original_url` is filled only by Test Connection. The derived domain is the one
        the connector already talks to, so no shop is accepted that the integration is not connected to.

        :param integration: sale.integration record
        :return: tuple (bool, str) — verified flag and log message
        """
        verified, message = super()._verify_shop_domain(integration)
        if verified:
            return verified, message

        shop_domain = self.get_shop_domain(integration)
        api_domain = prepare_shopify_url(integration.get_settings_value('url', ''))

        if shop_domain and shop_domain == api_domain:
            return True, '%s webhook shop domain verified.' % integration.name

        # Name both sides of the comparison: a bare "invalid shop domain" gives support nothing to debug with
        accepted_domains = [
            domain for domain in (
                integration._truncate_settings_url(),
                integration.get_settings_value('original_url', ''),
                api_domain,
            ) if domain
        ]
        message = '%s webhook invalid shop domain "%s", expected one of: %s.' % (
            integration.name,
            shop_domain,
            ', '.join('"%s"' % domain for domain in dict.fromkeys(accepted_domains)) or 'none (Shop ID is empty)',
        )

        return False, message

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
            'REFUNDS_CREATE': '_process_refund_create',
            'RETURNS_REQUEST': '_process_return_event',
            'RETURNS_APPROVE': '_process_return_event',
            'RETURNS_CANCEL': '_process_return_event',
            'RETURNS_CLOSE': '_process_return_event',
            'RETURNS_DECLINE': '_process_return_event',
            'RETURNS_UPDATE': '_process_return_event',
        }

    def _process_event(self, integration, external_id):
        try:
            return super(ShopifyWebhook, self)._process_event(integration, external_id)
        except ShopifyResourceNotFoundError as ex:
            # Shopify returned no such order: deleted, or older than 60 days without read_all_orders.
            # A retry cannot change that, and an error answer would get the subscription deleted.
            message = f'Webhook skipped: {ex}'
            integration.env['integration.logging'].write_log(
                integration,
                'webhook',
                'order_not_found',
                message,
                log_level='warning',
            )
            return Response(message)

    # Handle orders
    @route(
        [
            f'/integration/<string:dbname>/{SHOPIFY}/<int:integration_id>/orders',
            f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/orders',
        ],
        **_kwargs,
    )
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

    # Handle refunds
    @route(
        [
            f'/integration/<string:dbname>/{SHOPIFY}/<int:integration_id>/refunds',
            f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/refunds',
        ],
        **_kwargs,
    )
    @build_environment
    @validate_integration
    def shopify_receive_refunds(self, *args, **kw):
        """
        Expected methods:
            REFUNDS_CREATE
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_refunds()')
        integration = request.env['sale.integration'].browse(kw['integration_id'])
        external_order_id = self._get_value_from_post_data('order_id')
        return self._process_event(integration, external_order_id)

    @with_webhook_context
    def _process_refund_create(self, integration, external_order_id):
        _logger.info(f'Call {integration.name} webhook controller method: _process_refund_create')
        data = self._prepare_pipeline_data(integration, external_order_id)

        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        integration.process_pipeline_by_id_with_delay(external_order_id, data, build_and_run=True)
        return Response(f'Job created for order with code={external_order_id}. Action: process refund create')

    # Handle returns
    @route(
        [
            f'/integration/<string:dbname>/{SHOPIFY}/<int:integration_id>/returns',
            f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/returns',
        ],
        **_kwargs,
    )
    @build_environment
    @validate_integration
    def shopify_receive_returns(self, *args, **kw):
        """
        Expected methods:
            RETURNS_REQUEST
            RETURNS_APPROVE
            RETURNS_CANCEL
            RETURNS_CLOSE
            RETURNS_DECLINE
            RETURNS_UPDATE
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_returns()')
        integration = request.env['sale.integration'].browse(kw['integration_id'])
        # Shopify is inconsistent across returns/* topics: some (e.g. returns/cancel) deliver a
        # flat top-level "order_id", others (e.g. returns/approve) nest it as "order": {"id": ...}
        # with no "order_id". Accept both. The payload's own top-level "id" is always the Return id,
        # never the order id. (Read the dict directly — _get_value_from_post_data raises on a missing
        # key, so it can't be used to probe one form then fall back to the other.)
        post_data = self._get_post_data()
        external_order_id = post_data.get('order_id')
        if not external_order_id:
            order_obj = post_data.get('order')
            if isinstance(order_obj, dict):
                external_order_id = order_obj.get('id')
        if not external_order_id:
            # returns/update carries neither. An error answer would only make Shopify retry the
            # event and then delete the subscription, so acknowledge it.
            message = f'Webhook skipped: no order reference in the "{self.get_webhook_topic()}" payload.'
            _logger.info(message)
            return Response(message)
        return self._process_event(integration, external_order_id)

    @with_webhook_context
    def _process_return_event(self, integration, external_order_id):
        topic = self.get_webhook_topic()
        _logger.info(f'Call {integration.name} webhook controller method: _process_return_event (topic={topic})')
        data = self._prepare_pipeline_data(integration, external_order_id)

        should_import, message = integration._handle_missing_order(
            external_order_id,
            data['integration_workflow_states'],
        )
        if should_import is not None:
            return Response(message)

        integration.process_pipeline_by_id_with_delay(external_order_id, data, build_and_run=True)
        return Response(f'Job created for order with code={external_order_id}. Action: process {topic}')

    # Handle products
    @route(
        [
            f'/integration/<string:dbname>/{SHOPIFY}/<int:integration_id>/products',
            f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/products',
        ],
        **_kwargs,
    )
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
