# See LICENSE file for full copyright and licensing details.

import json
import urllib
import logging
from time import time
from urllib.error import HTTPError

from .tools import TOO_MANY_REQUESTS, RESOURCE_NOT_FOUND, ClientError, ResourceNotFound
from . import GraphQlQuery as GQuery, catch_exception, extract_node


_logger = logging.getLogger(__name__)


class ShopifyGraphQL:

    _subclasses = []
    _request_limit = 250

    def __init__(self, site, token):
        self._site = site
        self.full_url = f'{site}/graphql.json'

        self.headers = {
            'Accept': 'application/json',
            'X-Shopify-Access-Token': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-Integration-Shopify/1.0',
        }

    def __repr__(self):
        return f'{self.__class__.__name__} [{self._site}]'

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        _logger.info('Registering subclass: %s', cls.__name__)
        ShopifyGraphQL._subclasses.append(cls)

        # Add the static attributes from the child class
        for key, value in kwargs.items():
            setattr(ShopifyGraphQL, key, value)

        # Add the collable attributes from the child class
        for name, method in cls.__dict__.items():
            if callable(method) and not name.startswith('__'):
                setattr(ShopifyGraphQL, name, method)

    @catch_exception
    def execute(self, query: str, variables: dict = None):
        try:
            result = self._execute(query, variables=variables)
        except HTTPError as ex:
            if ex.code == RESOURCE_NOT_FOUND:
                raise ResourceNotFound from ex
            elif ex.code == TOO_MANY_REQUESTS:
                raise ClientError from ex
            raise ex

        return json.loads(result)

    def _execute(self, query: str, variables: dict = None):
        payload = dict(query=query)
        if variables:
            payload['variables'] = variables

        request = urllib.request.Request(
            self.full_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=self.headers,
            method='POST',
        )

        tag = str(time())
        _logger.info('%s request [%s] --> %s...', self, tag, query.translate(str.maketrans('', '', ' \n\t\r'))[:100])

        response = urllib.request.urlopen(request)
        response_text = response.read().decode('utf-8')

        _logger.info('ShopifyGraphQL response [%s] --> %s...', tag, response_text[:100])
        return response_text

    @extract_node('data.shop.productTags.edges', list)
    def get_feature_values(self):
        result = self.execute(GQuery.GET_FEATURE_VALUES)
        return result

    @extract_node('data.productVariants.edges.0.node', dict)
    def get_product_id_by_reference(self, ref_name, ref_value):
        result = self.execute(GQuery.PRODUCT_ID_BY_REFERENCE % (ref_name, ref_value, ref_name))
        return result

    @extract_node('data.customer.metafields.edges', list)
    def get_customer_metafields_by_id(self, customer_id: str):
        result = self.execute(GQuery.METAFIELDS_BY_OBJECT_QUERY_TEMPLATE % ('customer', 'Customer', customer_id))
        return result

    @extract_node('data.order.metafields.edges', list)
    def get_order_metafields_by_id(self, order_id: str):
        result = self.execute(GQuery.METAFIELDS_BY_OBJECT_QUERY_TEMPLATE % ('order', 'Order', order_id))
        return result

    @extract_node('data.metafieldDefinitions.edges', list)
    def get_metafields(self, entity_name):
        result = self.execute(GQuery.METAFIELDS_QUERY_TEMPLATE % entity_name.upper())
        return result

    @extract_node('data.order.risk', dict)
    def get_order_risks_from_order_query(self, external_id: str):
        result = self.execute(GQuery.ORDER_RISKS_FROM_ORDERS_QUERY_TEMPLATE % external_id)
        return result

    @extract_node('data.product.media.edges.node.id', list)
    def get_template_media_image_ids(self, template_id: str):
        result = self.execute(GQuery.QUERY_GET_PRODUCT_MEDIA_IMAGES_IDS % template_id)
        return result

    @extract_node('data.productDeleteMedia', dict)
    def drop_product_images(self, template_id: str):
        media_ids = self.get_template_media_image_ids(template_id)

        result = self.execute(
            GQuery.MUTATION_DROP_PRODUCT_MEDIA_IMAGES,
            variables={
                'mediaIds': [x for x in media_ids if 'MediaImage' in x],
                'productId': f'gid://shopify/Product/{template_id}',
            },
        )
        return result

    @extract_node('data.publications.edges', list)
    def get_sale_channels(self):
        result = self.execute(GQuery.GET_SALE_CHANNELS)
        return result

    def get_taxes_from_orders_query(self, limit):
        return self.fetch_orders_batch(GQuery.TAXES_FROM_ORDERS_QUERY_TEMPLATE, limit)

    def get_payment_methods_from_orders_query(self, limit):
        return self.fetch_orders_batch(GQuery.PAYMENT_METHODS_FROM_ORDERS_QUERY_TEMPLATE, limit)

    def get_delivery_methods_from_orders_query(self, limit):
        return self.fetch_orders_batch(GQuery.DELIVERY_METHODS_FROM_ORDERS_QUERY_TEMPLATE, limit)

    def fetch_orders_batch(self, query_template, limit: int):
        result, cursor = list(), ''
        _params = f'first: {self._request_limit}, sortKey: CREATED_AT, reverse: true'

        for _ in range((limit // self._request_limit) + 1):
            params = f'{_params}, after: "{cursor}"' if cursor else _params
            response = self._fetch_orders_batch(query_template % params)

            result.extend(response.get('edges', []))
            cursor = response.get('pageInfo', {}).get('endCursor')

            if not cursor or len(result) >= limit:
                break

        return result[:limit]

    @extract_node('data.orders', dict)
    def _fetch_orders_batch(self, query):
        result = self.execute(query)
        return result

    @extract_node('data.orderCancel', dict)
    def cancel_order(self, external_id: str, params: dict):
        query = GQuery.CANCEL_ORDER % (
            external_id,
            params['notify_cutomer'],
            params['refund'],
            params['restock'],
            params['reason'],
            params['staff_note'],
        )
        result = self.execute(query)
        return result

    @extract_node('data.fulfillmentCancel', dict)
    def cancel_fulfillment(self, external_id: str):
        result = self.execute(GQuery.CANCEL_FULFILLMENT % external_id)
        return result

    @extract_node('data.order', dict)
    def fetch_order(self, external_id: str):
        result = self.execute(GQuery.ORDER_BY_ID % external_id)
        return result

    def get_orders_ids_query(self, order_ids):
        if not isinstance(order_ids, list):
            order_ids = [order_ids]
        return self.fetch_orders_by_ids(GQuery.CHANNEL_ID_FROM_ORDERS, order_ids)

    def fetch_orders_by_ids(self, query_template, order_ids: list):
        """
        Fetch orders from Shopify GraphQL API based on provided order IDs.
        """
        if not order_ids:
            return []

        ids_query = ' OR '.join(f'id:{order_id}' for order_id in order_ids)
        params = f'first: {len(order_ids)}, query: "{ids_query}"'

        response = self._fetch_orders_batch(query_template % params)

        return response.get('edges', [])
