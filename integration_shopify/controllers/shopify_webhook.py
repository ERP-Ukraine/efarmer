#  See LICENSE file for full copyright and licensing details.

import json
import hmac
import base64
from hashlib import sha256
import logging

from odoo.http import Controller, route, request
from odoo.addons.integration.controllers.integration_webhook import IntegrationWebhook
from odoo.addons.integration.controllers.utils import build_environment, validate_integration

from ..shopify_api import SHOPIFY
from ..shopify.shopify_order import ShopifyOrder


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
    NEW_ORDER_METHOD_NAME = 'orders_create'
    NEW_PRODUCT_METHOD_NAME = 'products_create'

    @property
    def integration_type(self):
        return SHOPIFY

    @route(f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/orders', **_kwargs)
    @build_environment
    @validate_integration
    def shopify_receive_orders(self, *args, **kw):
        """
        Expected methods:
            orders/create
            orders/paid
            orders/cancelled
            orders/fulfilled
            orders/partially_fulfilled
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_orders()')
        integration = request.env['sale.integration'].browse(kw['integration_id'])
        return self.receive_order_generic(integration)

    @route(f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/products', **_kwargs)
    @build_environment
    @validate_integration
    def shopify_receive_products(self, *args, **kw):
        """
        Expected methods:
            products/create
            products/update
            products/delete
        """
        _logger.info('Call shopify webhook controller method: shopify_receive_products()')
        integration = request.env['sale.integration'].browse(kw['integration_id'])
        external_product_id = str(self._get_value_from_post_data('id'))
        return self.receive_product_generic(integration, external_product_id)

    def orders_paid(self, input_file, *args, **kw):
        _logger.info('Call shopify webhook controller method: orders_paid()')
        return self._receive_order(input_file)

    def orders_cancelled(self, input_file, *args, **kw):
        _logger.info('Call shopify webhook controller method: orders_cancelled()')
        data = self._prepare_pipeline_data()
        return input_file._run_cancel_order(data)

    def orders_fulfilled(self, input_file, *args, **kw):
        _logger.info('Call shopify webhook controller method: orders_fulfilled()')
        return self._receive_order(input_file)

    def orders_partially_fulfilled(self, input_file, *args, **kw):
        _logger.info('Call shopify webhook controller method: orders_partially_fulfilled()')
        return self._receive_order(input_file)

    def orders_create(self, integration, external_order_id):
        _logger.info('Call shopify webhook controller: orders_create()')
        return integration.integration_receive_orders_cron(cron_operation=False)  # TODO: by ID

    def products_create(self, integration, external_product_id):
        _logger.info('Call shopify webhook controller: products_create()')

        name = self._get_value_from_post_data('title')

        job_kwargs = integration._job_kwargs_import_product(external_product_id, name)
        job_kwargs['description'] = (
            f'{integration.name}: Create External Product By ID "{name}" [{external_product_id}]'
            ' + auto-matching [webhook action]'
        )
        job = integration.with_context(company_id=integration.company_id.id)\
            .with_delay(**job_kwargs)\
            .create_external_template_by_id(
                external_product_id,
                create_new_product=integration.auto_create_products_on_so,
            )

        integration.job_log(job)

        return job

    def products_update(self, integration, odoo_external_product_id):
        _logger.info('Call shopify webhook controller: products_update()')

        record = request.env['integration.product.template.external'].browse(odoo_external_product_id)

        job_kwargs = integration._job_kwargs_import_product(record.code, record.name)
        job_kwargs['description'] = (
            f'{integration.name}: Refresh External Product "{record.name}" [{record.code}] [webhook action]'
        )
        job = integration.with_context(company_id=integration.company_id.id)\
            .with_delay(**job_kwargs)\
            .import_product(record.id, import_images=True)

        integration.job_log(job)

        return job

    def products_delete(self, integration, odoo_external_product_id):
        _logger.info('Call shopify webhook controller: products_delete()')

        record = request.env['integration.product.template.external'].browse(odoo_external_product_id)

        job = integration.with_context(company_id=integration.company_id.id)\
            .with_delay(
                description=(
                    f'{integration.name}: Unlink External Odoo Record "{record.name}" [{record.code}] [webhook action]'
                ),
            ).drop_external_record(odoo_external_product_id)

        integration.job_log(job)

        return job

    def _receive_order(self, input_file):
        data = self._prepare_pipeline_data()
        return input_file._build_and_run_order_pipeline(data)

    def _prepare_pipeline_data(self):
        post_data = self._get_post_data()
        vals = {
            'external_tags': ShopifyOrder._parse_tags(post_data),
            'payment_method': ShopifyOrder._parse_payment_code(post_data),
            'integration_workflow_states': ShopifyOrder._parse_workflow_states(post_data),
        }
        return vals

    def _check_webhook_digital_sign(self, integration):
        # https://shopify.dev/apps/webhooks/configuration/https#verify-a-webhook
        headers = self._get_headers()
        hmac_header = headers.get('X-Shopify-Hmac-Sha256')

        post_data = self._get_post_data()
        api_secret_key = integration.get_settings_value('secret_key')
        data = json.dumps(post_data).encode('utf-8')

        digest = hmac.new(api_secret_key.encode('utf-8'), data, digestmod=sha256).digest()
        computed_hmac = base64.b64encode(digest)

        result = hmac.compare_digest(computed_hmac, hmac_header.encode('utf-8'))  # TODO
        _logger.info('Shopify webhook digital sign: %s', result)
        return True

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
