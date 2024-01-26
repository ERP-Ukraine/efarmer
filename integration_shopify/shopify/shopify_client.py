#  See LICENSE file for full copyright and licensing details.

from urllib.error import HTTPError

from .exceptions import ShopifyApiException
from .tools import ClientError, ResourceNotFound
from .tools import catch_exception, TOO_MANY_REQUESTS, RESOURCE_NOT_FOUND

from odoo import _
from odoo.exceptions import UserError, ValidationError

import json
import logging
import requests

_logger = logging.getLogger(__name__)

try:
    from shopify import (
        Session,
        AccessScope,
        ShopifyResource,
        Country,
        Image,
        Shop,
        Order,
        Product,
        Variant,
        FulfillmentOrders,
        Collect,
        CustomCollection,
        InventoryItem,
        InventoryLevel,
        Webhook,
        Customer,
        GraphQL,
        Transaction,
        Metafield,
        Location,
        OrderRisk,
    )
    from shopify.resources.fulfillment import FulfillmentV2
except (ImportError, IOError) as ex:
    _logger.error(ex)


SHOP = 'shop'
ORDER = 'order'
TEMPLATE = 'product'
VARIANT = 'variant'
IMAGE = 'image'
COUNTRY = 'country'
FULFILLMENT = 'fulfillment'
FULFILLMENT_ORDER = 'fulfillment_order'
COLLECT = 'collect'
CATEGORY = 'category'
INVENT_ITEM = 'inventory_item'
INVENT_LEVEL = 'inventory_level'
ACCESS_SCOPE = 'access_scope'
WEBHOOK = 'webhook'
CUSTOMER = 'customer'
TRANSACTION = 'transaction'
METAFIELD = 'metafield'
LOCATION = 'location'
ORDER_RISK = 'order_risk'

SHOPIFY_FETCH_LIMIT = 250


class CurrentShop(Shop):

    _singular = 'shop'
    _plural = 'shops'

    @catch_exception
    def _fetch_current(self):
        return self.__class__.current()


class WebhookPatch(Webhook):

    _singular = 'webhook'
    _plural = 'webhooks'

    @catch_exception
    def save(self):
        """
        Redefined method because of we need to POST `webhook` in other way than just a common
        post-request. I don't know why it's not implemented in the ShopifyAPI Lib.
        """
        if not self.is_new():
            return super(WebhookPatch, self).save()

        url = self._build_post_url()
        headers = self._build_post_headers()
        data = {
            'webhook': self.to_dict(),
        }
        response = self._send_request('POST', url, headers=headers, data=data)

        self._update(self.__class__.format.decode(response.content))
        return self

    def _send_request(self, method, url, params=None, headers=None, data=None):
        _logger.debug('%s %s %s %s', method, url, params, data)

        response = requests.request(
            method,
            url,
            params=params,
            json=data,
            headers=headers,
        )

        self._check_response(response)
        return response

    def _build_post_url(self):
        return f'{self._site}/webhooks.json'

    def _build_post_headers(self):
        headers = self.klass.headers
        headers['Content-Type'] = 'application/json'
        return headers

    def _check_response(self, response):
        if not response.ok:
            raise ShopifyApiException(response.text)


class CustomCollectionPatch(CustomCollection):

    _singular = 'custom_collection'
    _plural = 'custom_collections'

    @catch_exception
    def add_product(self, product):
        return super(CustomCollectionPatch, self).add_product(product)

    @catch_exception
    def remove_product(self, product):
        return super(CustomCollectionPatch, self).remove_product(product)


class Client:

    classes = {
        SHOP: CurrentShop,
        ORDER: Order,
        TEMPLATE: Product,
        VARIANT: Variant,
        IMAGE: Image,
        COUNTRY: Country,
        FULFILLMENT: FulfillmentV2,
        FULFILLMENT_ORDER: FulfillmentOrders,
        COLLECT: Collect,
        CATEGORY: CustomCollectionPatch,
        INVENT_ITEM: InventoryItem,
        INVENT_LEVEL: InventoryLevel,
        ACCESS_SCOPE: AccessScope,
        WEBHOOK: WebhookPatch,
        CUSTOMER: Customer,
        TRANSACTION: Transaction,
        METAFIELD: Metafield,
        LOCATION: Location,
        ORDER_RISK: OrderRisk,
    }

    def __init__(self, settings):
        self._session = Session(
            settings['fields']['url']['value'],
            settings['fields']['version']['value'],
            settings['fields']['key']['value'],
        )
        self.activate_session()
        self.api_version = self._session.version.name
        self.shop = self._model_init(SHOP)._fetch_current()

    def __repr__(self):
        return f'<ShopifyClient ({self.shop.name}) at {hex(id(self))}>'

    def deactivate_session(self):
        ShopifyResource.clear_session()

    def activate_session(self):
        ShopifyResource.activate_session(self._session)

    def _model(self, name):
        if name not in self.classes:
            raise UserError(_(
                'Unsupported shopify client model name: %s.' % name
            ))

        return self.classes[name]

    def _model_init(self, name, **kw):
        return self._model(name)(**kw)

    def _get_admin_url(self):
        return f'{self._session.protocol}://{self._session.url}/admin'

    def _get_access_scope(self):
        scopes = self._fetch_multi(ACCESS_SCOPE, None, None, None)
        return [scope.handle for scope in scopes]

    def _get_location_id(self):
        location = self.shop.primary_location_id
        if not location:
            raise ValidationError(_(
                'You have to specify Shop Location in your store admin settings.'
            ))
        return location

    def _get_weight_uom(self):
        return self.shop.weight_unit

    @catch_exception
    def _save(self, record):
        result = record.save()

        if not result:
            error = record.errors.errors
            record_json = record.to_json()
            _logger.error('Shopify  external-save-error: %s', error)
            _logger.error('Shopify record: %s', record_json)
            raise ShopifyApiException({'ERROR': error, 'RECORD': record_json})

        return result

    @catch_exception
    def _apply(self, name, *args):
        shopify_cls = self._model(name)
        return shopify_cls.set(*args)

    @catch_exception
    def _destroy(self, record):
        return record.destroy()

    @catch_exception
    def _refresh(self, record):
        return record.reload()

    @catch_exception
    def _fetch_one(self, name, record_id, fields):
        kwargs = dict()
        shopify_cls = self._model(name)

        if fields:
            fields.append('id')
            kwargs['fields'] = ','.join(set(fields))

        return shopify_cls.find(record_id, **kwargs)

    @catch_exception
    def _fetch_multi(self, name, params, fields, quantity):
        """
        Parameters:
            name: ShopifyAPI Resource py-library class-name
            params: dict
            fields: list
            quantity: int

        Important:
            Don't pass to params 'quantity' more than 250.
        """

        if quantity and quantity < SHOPIFY_FETCH_LIMIT:
            limit = quantity
        else:
            limit = SHOPIFY_FETCH_LIMIT

        kwargs = dict(limit=limit, order='id ASC')

        if params:
            kwargs.update(params)

        if fields:
            fields.append('id')
            kwargs['fields'] = ','.join(set(fields))

        shopify_cls = self._model(name)
        records = shopify_cls.find(**kwargs)
        result = list(records)

        if quantity and len(result) <= quantity:
            return result

        while records.next_page_url:
            records = shopify_cls.find(from_=records.next_page_url)
            result.extend(list(records))

            if quantity and len(result) <= quantity:
                break

        return result[:quantity]

    @catch_exception
    def _execute_graphql(self, query):
        try:
            result = GraphQL().execute(query)
        except HTTPError as ex:
            if ex.code == RESOURCE_NOT_FOUND:
                raise ResourceNotFound(ex)
            elif ex.code == TOO_MANY_REQUESTS:
                raise ClientError(ex)
            raise ex

        return json.loads(result)
