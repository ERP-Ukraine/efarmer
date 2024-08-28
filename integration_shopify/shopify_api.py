# See LICENSE file for full copyright and licensing details.

import base64
import logging
from operator import itemgetter
from itertools import chain, groupby
from collections import defaultdict

import requests
from dateutil import parser

from odoo import _
from odoo.addons.integration.api.abstract_apiclient import AbsApiClient
from odoo.addons.integration.models.fields.common_fields import GENERAL_GROUP
from odoo.addons.integration.tools import not_implemented, TemplateHub, add_dynamic_kwargs
from odoo.exceptions import UserError, ValidationError
from .shopify.tools import merge_orders_data, parse_graphql_id, ExtractNode

from .shopify import Client, ShopifyGraphQL, check_scope
from .shopify.exceptions import ShopifyApiException
from .shopify.shopify_client import (
    ORDER,
    TEMPLATE,
    VARIANT,
    IMAGE,
    COUNTRY,
    FULFILLMENT,
    FULFILLMENT_ORDER,
    COLLECT,
    CATEGORY,
    INVENT_LEVEL,
    WEBHOOK,
    CUSTOMER,
    TRANSACTION,
    SHOPIFY_FETCH_LIMIT,
)
from .shopify.shopify_helpers import ShopifyOrderStatus, ShopifyTxnStatus as Txn
from .shopify.shopify_client import METAFIELD, LOCATION
from .shopify.shopify_order import (
    ShopifyOrder,
    format_delivery_code,
    format_attr_code,
    format_attr_value_code,
    format_payment_code,
)


SHOPIFY = 'shopify'
ATTR_DEFAULT_TITLE = 'Title'  # Default product attribute name according to the Shopify API
ATTR_DEFAULT_VALUE = 'Default Title'  # Default product attribute value according to the Shopify API
METAFIELDS_NAME = 'metafields'

_logger = logging.getLogger(__name__)


class ShopifyAPIClient(AbsApiClient):

    settings_fields = (
        ('url', 'Shop URL', ''),
        ('version', 'API Version', ''),
        ('key', 'Admin API access token', ''),
        ('secret_key', 'API Secret Key', '', False, True),
        ('graphql_version', 'GraphQl Version', '2024-04'),
        ('import_products_filter', 'Import Products Filter', '{"status": "active"}', True),
        (
            'receive_order_statuses',
            'Order statuses separated by comma',
            ShopifyOrderStatus.STATUS_OPEN,
        ),
        (
            'receive_order_financial_statuses',
            'Order financial statuses separated by comma',
            ShopifyOrderStatus.SPECIAL_STATUS_ANY,
        ),
        (
            'receive_order_fulfillment_statuses',
            'Order fulfillment statuses separated by comma',
            ShopifyOrderStatus.SPECIAL_STATUS_ANY,
        ),
        ('weight_uom', 'Shopify weight unit. '
                       'Will be automatically populated when integration is active', '',),
        ('adapter_version', 'Version number of the api client', '0'),
        ('decimal_precision', 'Number of decimal places in the price of the exported product', '2'),
        ('batch_size', 'Number of orders processed in one batch', '1000'),
    )

    def __init__(self, settings):
        super().__init__(settings)

        self._client = Client(settings)
        self._graphql = ShopifyGraphQL(
            site=self._client._session.site.rsplit('/', maxsplit=1)[0] + '/'
            + settings['fields']['graphql_version']['value'],
            token=self._client._session.token,
        )
        self.country = self._client.shop.country
        self.lang = self._client.shop.primary_locale
        self.location_id = self._client._get_location_id()
        self.access_scopes = self._client._get_access_scope()
        self.admin_url = self._client._get_admin_url()
        self._weight_uom = self.get_settings_value('weight_uom')

    def deactivate_adapter(self):
        self._client.deactivate_session()

    def activate_adapter(self):
        self._client.activate_session()

    def check_connection(self):
        """TODO"""
        return True

    def get_api_resources(self):
        return

    def save(self, record):
        return self._client._save(record)

    def apply(self, name, *args):
        # Currently it used for the wrapping InventoryLevel `set` method
        return self._client._apply(name, *args)

    def destroy(self, record):
        return self._client._destroy(record)

    def refresh(self, record):
        return self._client._refresh(record)

    def model(self, name):
        return self._client._model(name)

    def model_init(self, name, **kw):
        return self._client._model_init(name, **kw)

    def fetch_one(self, name, record_id, fields=None):
        if not record_id:
            return self.model_init(name)

        result = self._client._fetch_one(name, record_id, fields)
        if not result:
            return self.model_init(name)

        return result

    def fetch_multi(self, name, params=None, fields=None, quantity=None):
        return self._client._fetch_multi(name, params, fields, quantity)

    def count(self, name):
        return self._client._model(name).count()

    def validate_template(self, template):
        _logger.info('Shopify: validate_template()')
        mappings_to_delete = []

        # (1) if template with such external id exists?
        shopify_product_id = template['external_id']
        if shopify_product_id:
            shopify_product = self.fetch_one(TEMPLATE, shopify_product_id)

            if shopify_product.is_new():
                mappings_to_delete.append({
                    'model': 'product.template',
                    'external_id': shopify_product_id,
                })

        # (2) if part of the variants has no external_id?
        mappings_to_update = self.parse_mappings_to_update(template['products'])

        # (3) if variant with such external id exists?
        for variant in template['products']:
            shopify_variant_id = self._parse_variant_id(variant['external_id'])
            if shopify_variant_id:
                shopify_variant = self.fetch_one(VARIANT, shopify_variant_id)

                if shopify_variant.is_new():
                    mappings_to_delete.append({
                        'model': 'product.product',
                        'external_id': variant['external_id'],
                    })

        return mappings_to_delete, mappings_to_update

    @add_dynamic_kwargs
    def find_existing_template(self, template, **kw):
        _logger.info('Shopify: find_existing_template()')
        # we try to search existing product template ONLY if there is no external_id for it
        # If there is external ID then we already mapped products and we do not need to search
        if template['external_id']:
            return False

        # Now let's validate if there are no duplicated references in Shopify
        variants = template['products']
        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name

        product_refs = [x['fields'].get(variant_reference) for x in variants]

        # Let's validate if all found products belong to the same product template
        ids_set = self._find_product_by_references(product_refs)(**kw)
        ids_set_product = [x[0] for x in ids_set if x[0]]

        # If nothing found, then just return False
        if not ids_set_product:
            return False

        # If more than one product id found - then we found references,
        # but they all belong to different products and we need to inform user about it
        # So he can fix on Shopify side
        # Because in Odoo it is single product template, and in Shopify - separate
        # product templates. That should not be allowed. Note that after previous check on
        # duplicates most likely it will not be possible, this check is just to be 100% sure
        if len(set(ids_set_product)) > 1:
            error_message = _(
                'Product reference(s) "%s" were found in multiple Shopify '
                'Products: %s. This is not allowed as in Odoo same references '
                'already belong to single product template and its variants. '
                'Structure of Odoo products and Shopify Products should be the same!'
            ) % (', '.join(product_refs), ', '.join(ids_set_product))
            raise UserError(error_message)

        shopify_product_id = ids_set_product[0]

        # Check if products in Odoo has the same amount of variants as in Shopify
        product = self.fetch_one(TEMPLATE, shopify_product_id)
        product_combination_ids = product.variants
        # counting expected variants excluding "virtual" variant
        # template_variants_count = len([x for x in variants if x['attribute_values']])
        if len(product_refs) != len(product_combination_ids):
            raise UserError(
                _(
                    'Amount of combinations in Shopify is %d. While amount in Odoo is %d. '
                    'Please, check the product with id %s in Shopify and make sure it has the same '
                    'amount of combinations as variants in Odoo (with enabled integration "%s").'
                ) % (
                    len(product_combination_ids),
                    len(product_refs),
                    shopify_product_id,
                    self._integration_name,
                )
            )

        attribute_value_tmpl_ids = self._attribute_value_from_template(product)

        for combination in product_combination_ids:
            # Make sure that reference is set on the combination
            reference = getattr(combination, variant_reference)

            if not reference:
                error_message = _('Product with id "%s" do not have references on '
                                  'all combinations. Please, add them and relaunch '
                                  'product export') % shopify_product_id
                raise UserError(error_message)

            attribute_values_from_shopify = self._attribute_value_from_variant(
                combination,
                attribute_value_tmpl_ids,
            )

            current_odoo_variant = list(
                filter(lambda x: x['fields'].get(variant_reference) == reference, variants)
            )
            if len(current_odoo_variant) == 0:
                error_message = _(
                    'There is no variant in Odoo with reference "%s" '
                    'that corresponds to Shopify product %s.'
                ) % (reference, shopify_product_id)
                raise UserError(error_message)

            attribute_values_from_odoo = list()
            attribute_values = current_odoo_variant[0]['attribute_values']

            for values in attribute_values:
                key = values['key']
                value = values['value']

                attribute_value_id = format_attr_value_code(key, value)
                attribute_values_from_odoo.append(attribute_value_id)

            if not (set(attribute_values_from_odoo) == set(attribute_values_from_shopify)):
                error_message = _(
                    'Shopify Variant with reference %s has variant values %s. While same '
                    'Odoo Variant has attribute values %s. Products in Shopify and Odoo '
                    'with the same reference should have the same combination of attributes.'
                ) % (
                    reference,
                    attribute_values_from_shopify,
                    attribute_values_from_odoo,
                )
                raise UserError(error_message)

        return shopify_product_id

    def create_webhooks_from_routes(self, routes_dict):
        result = dict()

        for name_tuple, route in routes_dict.items():
            webhook = self.model_init(WEBHOOK)

            webhook.address = route
            webhook.topic = name_tuple[-1]  # --> technical_name

            self.save(webhook)
            result[name_tuple] = str(webhook.id)

        return result

    def unlink_existing_webhooks(self, external_ids=None):
        if not external_ids:
            return False

        existing_webhooks = self.fetch_multi(WEBHOOK)

        for record in existing_webhooks:
            if str(record.id) in external_ids:
                self.destroy(record)

        return True

    @check_scope('write_products')
    def export_template(self, tmpl_data):
        _logger.info('Shopify: export_template()')

        tmpl_data['product_type'] = tmpl_data.pop('type')
        first_time_export = not bool(tmpl_data['external_id'])

        # Take metafields from tmpl_data
        meta_template_key = f'product.template.{str(tmpl_data["id"])}'
        meta_fields_vals = {meta_template_key: tmpl_data['fields'].pop(METAFIELDS_NAME, [])}

        for variant_data in tmpl_data['products']:
            meta_variant_key = f'product.product.{str(variant_data["id"])}'
            meta_fields_vals[meta_variant_key] = variant_data['fields'].pop(METAFIELDS_NAME, [])

        # Create or update product
        product = self.fetch_one(TEMPLATE, tmpl_data['external_id'])

        if first_time_export:
            self._attach_variants(product, tmpl_data['products'])
        else:
            self._update_variants(product, tmpl_data['products'])

        self._set_base_values(product, tmpl_data['fields'])
        # product.errors.full_messages()
        self.save(product)

        # Manage Collections
        if 'collections' in tmpl_data['fields']:
            collection_ids = [
                int(x) for x in tmpl_data['fields']['collections']
            ]
            collects = self.fetch_multi(
                COLLECT,
                params={
                    'product_id': product.id,
                },
            )
            for collection_id in [x.collection_id for x in collects]:
                if collection_id not in collection_ids:
                    collection = self.fetch_one(CATEGORY, collection_id)
                    collection.remove_product(product)

            for collection_id in collection_ids:
                collection = self.fetch_one(CATEGORY, collection_id)
                collection.add_product(product)

        mappings = self._serialize_mappings(product, tmpl_data)

        self._update_metafields(meta_fields_vals, mappings)

        return mappings

    def _update_metafields(self, meta_fields_vals, mappings):
        for mapping in mappings:
            if mapping['model'] == 'product.template':
                tmpl_params = {
                    'resource': 'products',
                    'resource_id': int(mapping['external_id']),
                }
            else:
                tmpl_params = {
                    'resource': 'variants',
                    'resource_id': self._parse_variant_id(mapping['external_id']),
                }

            meta_template_key = f'{mapping["model"]}.{str(mapping["id"])}'
            meta_vals = meta_fields_vals.get(meta_template_key)

            if not meta_vals:
                continue

            meta_fields = self.fetch_multi(METAFIELD, params=tmpl_params)

            for vals in meta_vals:
                meta_field = list(filter(lambda x: x.key == vals['key'], meta_fields))
                if meta_field:
                    meta_field = meta_field[0]

                    if not vals['value']:
                        self.destroy(meta_field)
                else:
                    meta_field = self.model_init(METAFIELD, prefix_options=tmpl_params)
                    meta_field.key = vals['key']
                    meta_field.namespace = vals['namespace']
                    meta_field.type = vals['type']

                if not vals['value']:
                    continue

                meta_field.value = vals['value']

                if not self.save(meta_field):
                    raise ShopifyApiException(_(
                        'Can\'t export metafield "%s" for "%s". '
                        'Please, check "Technical Name" and ''"Metafield Type" in '
                        'e-Commerce Integration->Product Fields->All Product Fields'
                    ) % (vals['key'], tmpl_params['resource']))

        return True

    @check_scope('write_products')
    def export_images(self, img_data):
        _logger.info('Shopify: export_images()')
        template_id = img_data['template']['id']

        # 1. Drop all existing images
        res = self._graphql.drop_product_images(template_id)

        if res.get('mediaUserErrors'):
            raise UserError(str(res['mediaUserErrors']))

        image_list = []

        # 2. Init template images
        if img_data['template']['default']:
            variant_ids = [self._parse_variant_id(x['id']) for x in img_data['products']]
            img = self._init_image(img_data['template']['default']['data'], template_id, variant_ids=variant_ids)
            image_list.append(img)

        for data in img_data['template']['extra']:
            img = self._init_image(data['data'], template_id, variant_ids=[])
            image_list.append(img)

        # 3. Init variants images
        for data in img_data['products']:
            variant_id = self._parse_variant_id(data['id'])

            if data['default']:
                img = self._init_image(data['default']['data'], template_id, variant_ids=[variant_id])
                image_list.append(img)

            for extra_image in data['extra']:
                img = self._init_image(extra_image['data'], template_id, variant_ids=[variant_id])
                image_list.append(img)

        # 4. Save images
        template = self.fetch_one(TEMPLATE, template_id)

        while image_list:  # Sending images by batches
            template.images.extend(image_list[:15])
            self.save(template)

            image_list = image_list[15:]

        return True

    @not_implemented
    def export_attribute(self, attribute):
        """
        There is no Shopify REST API endpoint for `Attributes`.
        Moreover, the is no way to reuse attribute ID because for the each productsthe same
        attributes will create the brand new attribute ID (id + product_id have to be unique).
        See the `_handle_mapping_data` method in integration class.

        :Template options:

            "options": [
                {
                    "id": 10578321309988,
                    "product_id": 8335897788708,
                    "name": "Size",
                    "position": 1,
                    "values": [
                        "UK 1",
                        "UK 2",
                    ]
                },
            ]

        """
        pass

    @not_implemented
    def export_attribute_value(self, attribute_value):
        """
        There is no Shopify REST API endpoint for `Attribute-Values`
        and there is no ID for shopify value, only name.
        See the `_handle_mapping_data` method in integration.
        """
        pass

    @not_implemented
    def export_feature(self, feature):
        pass

    def export_feature_value(self, feature_value):
        _logger.info('Shopify: export_feature_value().')
        return feature_value['name']

    @check_scope('write_products')
    def export_category(self, category):
        _logger.info('Shopify: export_category()')

        shopify_category = self.model_init(CATEGORY)
        shopify_category.title = category['name']
        self.save(shopify_category)
        return str(shopify_category.id)

    @check_scope('write_products', 'write_inventory')
    def export_inventory(self, inventory):
        _logger.info('Shopify: export_inventory()')

        results = list()
        default_location_id = self.location_id

        for external_id, inventory_item_list in inventory.items():
            variant_id = self._parse_variant_id(external_id)
            shopify_variant = self.fetch_one(VARIANT, variant_id)

            if shopify_variant.is_new():
                message = _('External product "%s" does not exist') % variant_id
                results.append((variant_id, None, message))
                continue

            if getattr(shopify_variant, 'inventory_management', '') != SHOPIFY:
                shopify_variant.inventory_management = SHOPIFY  # TODO: need to think
                res = self.save(shopify_variant)
                if not res:
                    message = _('Inventory management for product "%s" was not saved') % variant_id
                    results.append((variant_id, res, message))
                    continue

            item_result = list()
            for inventory_item in inventory_item_list:
                location_id = inventory_item['external_location_id'] or default_location_id

                args = (
                    int(location_id),
                    shopify_variant.inventory_item_id,
                    int(inventory_item['qty']),
                )
                res = self.apply(INVENT_LEVEL, *args)

                res_data = dict(
                    inventory_item_id=res.inventory_item_id,
                    location_id=res.location_id,
                    available=res.available,
                )
                item_result.append(res_data)

            results.append((external_id, item_result, ''))

        return results

    @check_scope(
        'write_fulfillments',
        'write_merchant_managed_fulfillment_orders',
    )
    def export_tracking(self, sale_order_id, tracking_data_list, force_done=False):
        if not all(x.get('external_location_id') for x in tracking_data_list):
            return self._export_tracking(sale_order_id, tracking_data_list)

        # Group tracking data by external location
        grouped_data = defaultdict(list)
        for key, grouper in groupby(tracking_data_list, key=itemgetter('external_location_id')):
            for value in grouper:
                grouped_data[key].append(value)

        # Fulfill order step by step with the `force done` flag on the last iteration
        result_list = list()
        for __, data_list in grouped_data.items():
            for idx, data in enumerate(data_list, start=1):
                result = self.send_picking(sale_order_id, data, force_done=(force_done and idx == len(data_list)))
                result_list.append(result)

        return list(filter(None, result_list))

    def _export_tracking(self, sale_order_id, tracking_data_list):
        """
        Force done the all `opened` fulfillment orders sorted by the max pending quantity.
        This method is suitable for the cases when an `external_location_id`
        not specified in the tracking_data_list.
        """
        fulfill_orders = self.fetch_fulfillment_orders(sale_order_id)

        fulfill_orders = sorted([
            x for x in fulfill_orders if x.status in ('open', 'in_progress')
            and x.line_items
        ], key=lambda x: len(x._get_pending_line_ids()))

        result_list = list()

        if not fulfill_orders:
            return result_list

        refs = [x['tracking'] for x in tracking_data_list if x['tracking']]

        for order_index, order in enumerate(fulfill_orders, start=1):
            fulfillment = self.model_init(FULFILLMENT)
            # 1. Fulfill all pending lines
            line_items = order._prepare_pending_lines()
            fulfillment.line_items_by_fulfillment_order = [{
                'fulfillment_order_id': order.id,
                'fulfillment_order_line_items': line_items,
            }]

            # 2. Assign suitable tracking-data: here may be many cases but to backorders etc.
            pending_ids = order._get_pending_line_ids()

            tracking_data = None
            for data in sorted(tracking_data_list, key=lambda x: len(x['lines'])):
                tracking = data['tracking']
                line_ids = [int(x['id']) for x in data['lines'] if tracking]

                if set(pending_ids).intersection(set(line_ids)) and (tracking in refs):
                    tracking_data = data
                    break

            if tracking_data:
                tracking = tracking_data['tracking']
                refs.remove(tracking)

                # Due to the number of the serialized pickings may be greater than quantity
                # of the fulfillment orders. We need to send the rest of the possible
                # tracking numbers on the last iteration
                if order_index == len(fulfill_orders) and refs:
                    refs.insert(0, tracking)
                    tracking = ','.join(refs)

                fulfillment.tracking_info = {
                    'number': tracking,
                    'company': tracking_data['carrier'] or '',
                }
                fulfillment.notify_customer = True

            result = self.save(fulfillment)
            result_list.append(
                self._serialize_fulfillment(fulfillment.to_dict()) if result else False
            )

        return list(filter(None, result_list))

    @check_scope(
        'write_fulfillments',
        'write_merchant_managed_fulfillment_orders',
    )
    def send_picking(self, sale_order_id, tracking_data, force_done=False):
        fulfill_orders = self.fetch_fulfillment_orders(sale_order_id)
        fulfill_orders = [
            x for x in fulfill_orders if x.status in ('open', 'in_progress') and x.line_items
        ]

        location_id = tracking_data.get('external_location_id')
        if location_id:
            fulfill_orders = [
                x for x in fulfill_orders if x.assigned_location_id == int(location_id)
            ]

        if not fulfill_orders:
            return False

        order = fulfill_orders.pop(0)
        new_fulfillment = self.model_init('fulfillment')

        if force_done:
            # Preparing all the pending lines
            line_items = order._prepare_pending_lines()
        else:
            # Preparing line by ID for the requested quantity (if available)
            line_items = [
                order._prepare_pending_line(int(x['id']), int(x['qty']))
                for x in tracking_data['lines']
            ]

        line_items = list(filter(None, line_items))

        if line_items:
            new_fulfillment.tracking_info = {
                'number': tracking_data.get('tracking') or '',
                'company': tracking_data.get('carrier') or '',
            }
            new_fulfillment.line_items_by_fulfillment_order = [{
                'fulfillment_order_id': order.id,
                'fulfillment_order_line_items': line_items,
            }]
            new_fulfillment.notify_customer = True

        if not new_fulfillment.attributes:
            return False

        result = self.save(new_fulfillment)

        if not result:
            return False

        if force_done:
            # Force done the rest of the fulfillment orders
            for order in fulfill_orders:
                self.send_picking(sale_order_id, {}, force_done=True)

        return self._serialize_fulfillment(new_fulfillment.to_dict())

    @check_scope('write_orders')
    def export_sale_order_status(self, vals):
        method_name = f'_export_sub_status_{vals["status"]}'

        if hasattr(self, method_name):
            return getattr(self, method_name)(vals)

        raise NotImplementedError(f'Shopify method "{method_name}" is still not implemented.')

    def _export_sub_status_paid(self, vals):
        amount = vals['amount']
        currency = vals['currency']
        order_id = vals['order_id']

        order = self.fetch_one(ORDER, order_id)
        if not order.id or order.financial_status == ShopifyOrderStatus.STATUS_PAID:
            return dict()

        if order.financial_status == ShopifyOrderStatus.STATUS_PARTIALLY_PAID:  # TODO
            raise ValidationError(
                _('We do not support yet marking as paid for "Partially Paid" orders')
            )

        if order.financial_status == ShopifyOrderStatus.STATUS_PARTIALLY_REFUNDED:  # TODO
            raise ValidationError(
                _('We do not support yet marking as paid for "Partially Refunded" orders')
            )

        params = dict(order_id=order_id)
        txn_list = self.fetch_multi(TRANSACTION, params=params)
        except_ids = [
            x.parent_id for x in txn_list if x.kind == Txn.VOID and x.status == Txn.STATUS_SUCCESS
        ]
        txn_list = [
            x for x in txn_list if x.kind in (Txn.AUTH, Txn.SALE)
            and x.status in (Txn.STATUS_PENDING, Txn.STATUS_SUCCESS)
            and x.id not in except_ids
        ]

        parent = txn_list[-1] if txn_list else False
        txn = self.model_init(TRANSACTION, prefix_options=params)

        if not parent:
            txn.kind = Txn.SALE
            txn.source = Txn.SOURCE_EXTERNAL
            txn.amount = amount
            txn.currency = currency

        elif parent.kind == Txn.SALE:
            if parent.status == Txn.STATUS_PENDING:
                txn.kind = Txn.CAPTURE  # TODO: make sure that `parent.amount == amount`
                txn.parent_id = parent.id
            else:
                txn.kind = Txn.SALE
                txn.source = Txn.SOURCE_EXTERNAL
                txn.amount = amount
                txn.currency = currency

        else:
            if parent.status == Txn.STATUS_PENDING:  # TODO: do the math how to perform
                raise ValidationError(               # pending parent transaction without raising
                    _('Awaiting for the transaction: %s') % parent.to_dict()
                )

            txn.kind = Txn.CAPTURE
            txn.parent_id = parent.id
            txn.amount = amount
            txn.currency = currency

        result = self.save(txn)

        if not result:
            return dict()
        return txn.to_dict()

    @add_dynamic_kwargs
    def order_fetch_kwargs(self, **kw):
        integration = self._get_integration(kw)
        receive_from = integration.last_receive_orders_datetime_str
        cut_off_datetime = integration.orders_cut_off_datetime_str

        params = self._default_order_domain()
        params['updated_at_min'] = receive_from
        params['order'] = 'updated_at ASC'

        if cut_off_datetime:
            params['created_at_min'] = cut_off_datetime

        return {
            'params': params,
            'quantity': self.order_limit_value(),
        }

    def receive_orders_using_graphql(self, order_ids):
        """
        Fetch orders using GraphQL API.
        """
        order_graphql_ids = self._graphql.get_orders_ids_query(order_ids)

        # Process GraphQL data
        graphql_orders = []
        for order in order_graphql_ids:
            order_id = ExtractNode.extract_raw(order, 'node.id', str)
            channel_id = ExtractNode.extract_raw(order, 'node.publication.id', str)

            if order_id:
                graphql_orders.append({
                    "id": parse_graphql_id(order_id),
                    "channel_id": parse_graphql_id(channel_id) if channel_id else None,
                })

        return graphql_orders

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def receive_orders(self, **kw):
        _logger.info('Shopify: receive_orders()')

        # Fetch orders using REST API
        kwargs = self.order_fetch_kwargs()(**kw)
        orders = self.fetch_multi(ORDER, **kwargs)

        # Extract order IDs
        new_order_ids = [str(order.id) for order in orders]

        # If no orders found, return empty list
        if not new_order_ids:
            return []

        # Fetch additional order information using GraphQL API
        graphql_orders_data = self.receive_orders_using_graphql(new_order_ids)

        # Merge GraphQL data into orders.
        merge_orders_data(orders, graphql_orders_data, ['channel_id'])

        result = [
            {
                'id': str(order.id),
                'data': order.to_dict(),
                'updated_at': order.updated_at,
                'created_at': order.created_at,
            }
            for order in orders
        ]

        return result

    @check_scope('read_orders')
    def receive_order(self, order_id):
        """
        Receive and process a single order from Shopify.
        """
        # Fetch order from REST API
        order = self.fetch_one(ORDER, order_id)
        if order.is_new():
            return {}

        # Fetch order data from GraphQL API
        graphql_order_data = self._graphql.get_orders_ids_query(order_id)
        graphql_order = next(
            ExtractNode.extract_raw(order, 'node', str) or {}
            for order in graphql_order_data
        )

        # Update the order with the processed data
        publication = graphql_order.get('publication') or {}
        channel_id = parse_graphql_id(publication.get('id', ''))
        order.channel_id = channel_id

        # Prepare the final output
        return {
            'id': order.id,
            'data': order.to_dict()
        }

    def get_order_class_parser(self):
        """Hook for external module extensions"""
        return ShopifyOrder

    @add_dynamic_kwargs
    def parse_order(self, input_file: dict, **kw) -> dict:
        _logger.info('Shopify: parse_order() from input file.')

        fulfillment_orders = self.fetch_fulfillment_orders(input_file['id'])
        order_risks = self.fetch_order_risks(input_file['id'])
        order_transactions = self.fetch_order_payments(input_file['id'])

        ClassParser = self.get_order_class_parser()

        shopify_order = ClassParser(
            self._get_integration(kw),
            input_file,
            [x.to_dict() for x in fulfillment_orders],
            order_risks=order_risks,
            order_transactions=order_transactions,
        )

        return shopify_order.parse()

    @check_scope('read_orders')
    def fetch_order_risks(self, external_order_id: str, risklevel : str = 'HIGH'):
        """
        Fetch order risks from Shopify for a specific order.
        """
        risk_data = self._graphql.get_order_risks_from_order_query(external_order_id)
        if not risk_data:
            return list()

        risks = list()
        assessments = risk_data.get('assessments') or list()
        recommendation = risk_data.get('recommendation') or ''

        for record in assessments:
            if record.get('riskLevel') == risklevel:

                for fact in record.get('facts', []):
                    risks.append({
                        **fact,
                        'order_id': external_order_id,
                        'recommendation': recommendation.lower(),
                    })

        return risks

    @check_scope('read_orders')
    def fetch_order_payments(self, external_order_id):
        records = self.fetch_multi(TRANSACTION, params={'order_id': external_order_id})
        if not records:
            return list()

        records = filter(
            lambda x: x.status == 'success' and x.kind in ('capture', 'sale'), records
        )
        return [x.to_dict() for x in records]

    def fetch_fulfillments(self, external_order_id):
        order_data = self.receive_order(external_order_id)
        if not order_data:
            return list()

        fulfillments = order_data['data'].get('fulfillments') or list()
        return [self._serialize_fulfillment(x) for x in fulfillments]

    @add_dynamic_kwargs
    def get_delivery_methods(self, **kw):
        _logger.info('Shopify: get_delivery_methods()')

        integration = self._get_integration(kw)
        batch_size = int(integration.get_settings_value('batch_size'))

        order_edges = self._graphql.get_delivery_methods_from_orders_query(batch_size)

        delivery_set = set()
        for data in order_edges:
            delivery_set |= self._parse_delivery_methods(data.get('node'))

        return [dict(x) for x in delivery_set]

    def _parse_delivery_methods(self, order):
        shipping_methods = []
        for line in order.get('shippingLines', {}).get('nodes', []):
            title = line.get('title')
            code = line.get('code')
            ext_code = format_delivery_code(title, code)

            shipping_methods.append(
                (('id', ext_code), ('name', (title or code)))
            )

        return set(shipping_methods)

    def get_single_tax(self, tax_id):
        _logger.info('Shopify: get_single_tax(). No implemented')
        return dict()

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def get_taxes(self, **kw):
        _logger.info('Shopify: get_taxes()')

        integration = self._get_integration(kw)
        batch_size = int(integration.get_settings_value('batch_size'))

        order_edges = self._graphql.get_taxes_from_orders_query(batch_size)

        tax_set = set()
        for data in order_edges:
            tax_set |= self._parse_taxes(data.get('node'))

        format_to_external = integration._fetch_external_tax
        return [format_to_external(x) for x in tax_set]

    def _parse_taxes(self, order):
        tax_included = order.get('taxesIncluded')

        # Extract taxes from order tax lines
        order_tax_list = [
            self._format_tax(tax, tax_included)
            for tax in order.get('taxLines', [])
            if tax
        ]

        # Extract taxes from line item tax lines
        line_tax_list = [
            self._format_tax(tax, tax_included)
            for line in order.get('lineItems', {}).get('edges', [])
            for tax in line.get('node', {}).get('taxLines', [])
            if tax
        ]

        # Extract taxes from shipping line tax lines
        shipping_tax_list = [
            self._format_tax(tax, tax_included)
            for line in order.get('shippingLines', {}).get('edges', [])
            for tax in line.get('node', {}).get('taxLines', [])
            if tax
        ]
        return set(order_tax_list + line_tax_list + shipping_tax_list)

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def get_payment_methods(self, **kw):
        _logger.info('Shopify: get_payment_methods()')

        integration = self._get_integration(kw)
        batch_size = int(integration.get_settings_value('batch_size'))

        order_edges = self._graphql.get_payment_methods_from_orders_query(batch_size)

        empty_code = format_payment_code(None)
        payment_set = {(('id', empty_code), ('name', empty_code))}

        for data in order_edges:
            payment_set |= self._parse_payment_methods(data.get('node'))

        return [dict(x) for x in payment_set]

    def _parse_payment_methods(self, order):
        payment_methods = []
        for name in order.get('paymentGatewayNames', []):
            if not name:
                continue

            ext_code = format_payment_code(name)
            payment_methods.append(
                (('id', ext_code), ('name', name))
            )

        return set(payment_methods)

    def get_languages(self):
        _logger.info('Shopify: get_languages()')
        current_lang = {
            'id': self.lang,
            'code': self.lang,
            'external_reference': f'{self.lang}_{self.country}'
        }
        return [current_lang]

    @check_scope('read_products')
    def get_attributes(self, parse_values=False):
        _logger.info('Shopify: get_attributes()')

        products = self.fetch_multi(TEMPLATE, fields=['options'])

        result = set()
        for product in products:
            res = self._parse_attributes(product, parse_values=parse_values)
            result.update(res)

        return [dict(x) for x in result]

    def get_attribute_values(self):
        _logger.info('Shopify: get_attribute_values()')
        return self.get_attributes(parse_values=True)

    def get_features(self):
        _logger.info('Shopify: get_features()')
        return [{
            'id': GENERAL_GROUP,
            'name': 'General group',
        }]

    def get_feature_values(self):
        _logger.info('Shopify: get_feature_values()')
        tags = self._graphql.get_feature_values()

        return [
            {
                'id': x['node'],
                'name': x['node'],
                'id_group': GENERAL_GROUP,
            } for x in tags
        ]

    def get_pricelists(self):
        _logger.info('Shopify: get_pricelists(). Not implemented.')
        return []

    @check_scope('read_locations')
    def get_locations(self):
        _logger.info('Shopify: get_locations().')

        result = list()
        location_list = self.fetch_multi(LOCATION)

        for rec in location_list:
            vals = dict(
                id=str(rec.id),
                name=rec.name,
            )
            result.append(vals)

        return result

    def get_countries(self):
        _logger.info('Shopify: get_countries()')

        external_countries = list()
        countries = self.fetch_multi(COUNTRY, fields=['name', 'code'])

        for country in countries:
            external_country = {
                'id': str(country.id),
                'name': country.name,
                'external_reference': country.code,
            }
            external_countries.append(external_country)

        return external_countries

    def get_states(self):
        _logger.info('Shopify: get_states()')

        external_states = list()
        countries = self.fetch_multi(COUNTRY, fields=['name', 'code', 'provinces'])

        for country in countries:
            for state in country.provinces:
                external_state = {
                    'id': str(state.id),
                    'name': state.name,
                    'external_reference': f'{country.code}_{state.code}',
                }
                external_states.append(external_state)

        return external_states

    @check_scope('read_products')
    def get_categories(self):
        _logger.info('Shopify: get_categories()')

        external_collections = list()
        collections = self.fetch_multi(CATEGORY, fields=['title'])

        for collection in collections:
            external_state = {
                'id': str(collection.id),
                'name': collection.title,
            }
            external_collections.append(external_state)

        return external_collections

    def get_sale_order_statuses(self):
        _logger.info('Shopify: get_sale_order_statuses()')
        order_states = list()

        statuses = self._get_shopify_statuses()
        for state, values in statuses.items():
            order_states.append({
                'id': state,
                'name': values[0],
                'external_reference': False,
            })

        return order_states

    def get_product_template_ids(self):
        _logger.info('Shopify: get_product_template_ids()')

        params = self._default_product_domain()
        template_records = self.fetch_multi(
            TEMPLATE,
            params=params,
            fields=['id'],
        )
        return [x.id for x in template_records]

    @add_dynamic_kwargs
    @check_scope('read_products')
    def get_product_templates(self, template_ids, **kw):
        _logger.info('Shopify: get_product_templates()')

        if not template_ids:
            return dict()

        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name
        variant_barcode = integration.variant_barcode_api_name

        def parse_variant(template, variant):
            attribute_value_tmpl_ids = self._attribute_value_from_template(template)
            attribute_var_ids = self._attribute_value_from_variant(
                variant,
                attribute_value_tmpl_ids,
            )

            return {
                'id': self._build_product_external_code(template.id, variant.id),
                'name': template.title,
                'external_reference': getattr(variant, variant_reference) or None,
                'barcode': getattr(variant, variant_barcode) or None,
                'ext_product_template_id': str(template.id),
                'attribute_value_ids': attribute_var_ids,
            }

        result_list = list()
        templates = self.fetch_multi(
            TEMPLATE,
            params={
                'ids': ','.join(template_ids),
            },
            fields=['title', 'options', 'variants'],
        )

        for template in templates:
            external_ref = barcode = None
            variants = template.variants

            if len(variants) == 1:
                barcode = getattr(variants[0], variant_barcode) or None
                external_ref = getattr(variants[0], variant_reference) or None

            result_list.append({
                'id': str(template.id),
                'name': template.title,
                'barcode': barcode,
                'external_reference': external_ref,
                'variants': [parse_variant(template, x) for x in variants],
            })

        return {x['id']: x for x in result_list}

    @check_scope('read_customers')
    def get_customer_ids(self, date_since=None):
        _logger.info('Shopify: get_customer_ids()')
        customers = self.fetch_multi(CUSTOMER, fields=['id', 'updated_at'])

        if date_since:
            customers = [
                x for x in customers if
                parser.isoparse(x.updated_at).replace(tzinfo=None) > date_since
            ]
        return [x.id for x in customers]

    @check_scope('read_customers')
    def get_customer_and_addresses(self, customer_id):
        _logger.info('Shopify: get_customer_and_addresses()')
        parsed_customer, parsed_addreses = dict(), list()
        customer = self.fetch_one(CUSTOMER, customer_id)
        if customer.is_new():
            return parsed_customer, parsed_addreses

        customer = customer.to_dict()
        parsed_customer = self._parse_customer(customer)
        parsed_addreses = [
            self._parse_address(customer, x) for x in customer['addresses']
        ]
        return parsed_customer, parsed_addreses

    @check_scope('read_products', 'read_inventory')
    def get_product_for_import(self, product_code, import_images=False):
        _logger.info('Shopify: get_product_for_import()')

        product = self.fetch_one(TEMPLATE, product_code)
        if product.is_new():
            raise UserError(
                _('Product with id "%s" does not exist in Shopify') % product_code
            )

        images_hub = {
            'images': dict(),  # 'images': {'image_id': bin-data,}
            'variants': dict(),  # variants: {'variant_id': [image-ids],}
        }
        # Parse images
        if import_images:
            for image in product.images:
                response = requests.get(image.src)
                if response.status_code == 200:
                    images_hub['images'][str(image.id)] = response.content

        # Parse variants
        variants = list()
        for variant in product.variants:
            variant_id = self._build_product_external_code(product.id, variant.id)
            variants.append((product, variant))

            if import_images and variant.image_id:
                images_hub['variants'][variant_id] = [str(variant.image_id)]

        return product, variants, list(), images_hub  # TODO: convert `product` to dict

    def _attribute_value_from_template(self, template):
        attribute_value_tmpl_ids = list()

        for option in template.options:
            # If the attribute name is default and there is only one default value - skip it
            if (
                option.name == ATTR_DEFAULT_TITLE
                and len(option.values) == 1
                and option.values[0] == ATTR_DEFAULT_VALUE
            ):
                continue

            for value in option.values:
                attribute_value_tmpl_ids.append((option.name, value))

        return attribute_value_tmpl_ids

    def _attribute_value_from_variant(self, variant, attribute_value_tmpl_ids):
        attribute_var_ids = list()
        keys = self._get_option_keys()

        for variant_value in filter(None, [getattr(variant, key) for key in keys]):
            for (option_name, option_value) in attribute_value_tmpl_ids:
                if variant_value == option_value:
                    attribute_var_ids.append(
                        format_attr_value_code(option_name, option_value)
                    )

        return attribute_var_ids

    @not_implemented
    def get_products_for_accessories(self):
        pass

    @check_scope('read_products', 'read_inventory')
    def get_stock_levels(self, external_location_id):
        _logger.info('Shopify: get_stock_levels(%s)', external_location_id)

        stock_levels = self.fetch_multi(
            INVENT_LEVEL,
            params={
                'location_ids': external_location_id or self.location_id,
            },
            fields=['inventory_item_id', 'available'],
        )
        inventory_data = {x.inventory_item_id: x.available for x in stock_levels}

        result = dict()
        products = self.fetch_multi(TEMPLATE, fields=['id', 'variants'])
        for product in products:
            for variant in product.variants:
                item_id = variant.inventory_item_id

                if item_id in inventory_data:
                    code = self._build_product_external_code(product.id, variant.id)
                    result[code] = inventory_data[item_id]

        return result

    @add_dynamic_kwargs
    @check_scope('read_products')
    def get_templates_and_products_for_validation_test(self, product_refs=None, **kw):
        """Shopify product has no reference (sku) and barcode, only its variant."""
        _logger.info('Shopify: get_templates_and_products_for_validation_test()')

        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name
        variant_barcode = integration.variant_barcode_api_name

        def serialize_template(t):

            def serialize_variant(v):
                return {
                    'id': str(v['id']),
                    'name': v['title'],
                    'barcode': v.get(variant_barcode) or '',
                    'ref': v.get(variant_reference) or '',
                    'parent_id': str(t['id']),
                    'skip_ref': False,
                    'joint_namespace': False,
                }

            return [
                {
                    'id': str(t['id']),
                    'name': t['title'],
                    'barcode': '',
                    'ref': '',
                    'parent_id': '',
                    'skip_ref': True,
                    'joint_namespace': False,
                },
                *[serialize_variant(var) for var in t['variants']],
            ]

        params = self._default_product_domain()
        template_ids = self.fetch_multi(
            TEMPLATE,
            params=params,
            fields=['title', 'variants'],
        )
        products_data = dict()
        for tmpl in (template.to_dict() for template in template_ids):
            products_data[str(tmpl['id'])] = serialize_template(tmpl)

        return TemplateHub(list(chain.from_iterable(products_data.values())))

    @check_scope(
        'read_merchant_managed_fulfillment_orders',
        # 'read_assigned_fulfillment_orders',  # TODO
        # 'read_third_party_fulfillment_orders',  # TODO
    )
    def fetch_fulfillment_orders(self, external_order_id):
        return self.fetch_multi(
            FULFILLMENT_ORDER,
            params={
                'order_id': external_order_id,
            },
        )

    @check_scope('write_orders')
    def cancel_order(self, external_id: str, params: dict):
        return self._graphql.cancel_order(external_id, params)

    @check_scope('write_merchant_managed_fulfillment_orders')
    def cancel_fulfillment(self, external_id: str):
        return self._graphql.cancel_fulfillment(external_id)

    def _set_base_values(self, instance, data):
        for field, value in data.items():
            setattr(instance, field, value)

    def _init_image(self, data, product_id: str, variant_ids=False):
        image = self.model_init(IMAGE, prefix_options={'product_id': product_id})
        image.variant_ids = variant_ids or []
        image.attach_image(base64.b64decode(data))
        return image

    def _update_variants(self, product, variant_list):
        # Drop variants if necessary
        external_ids = [
            self._parse_variant_id(x['external_id']) for x in variant_list
        ]
        for variant in product.variants:
            if variant.id not in external_ids:
                self.destroy(variant)

        # Update variants
        self.refresh(product)
        self._attach_variants(product, variant_list)

    def _set_values(self, instance, data):
        self._set_base_values(instance, data['fields'])
        instance.inventory_management = SHOPIFY  # TODO: need to think

        keys = self._get_option_keys()
        values = [attr['value'] for attr in data['attribute_values']]

        for key, value in zip(keys, values):
            setattr(instance, key, value)

        return instance

    def _attach_variants(self, product, variant_list):
        product_options = defaultdict(list)
        existing_variants = getattr(product, 'variants', list())
        product.variants = list()

        for data in variant_list:
            variant_id = self._parse_variant_id(data['external_id'])
            variants = list(filter(lambda x: x.id == variant_id, existing_variants))
            variant = variants[0] if variants else self.fetch_one(VARIANT, variant_id)

            self._set_values(variant, data)
            product.variants.append(variant)

            for attr in data['attribute_values']:
                product_options[attr['key']].append(attr['value'])

        if product_options:  # avoid 'could not update options to []' shopify api error
            product.options = [
                {'name': k, 'values': v} for k, v in product_options.items()
            ]

    def _serialize_mappings(self, product, tmpl_data):
        mappings = [{
            'model': 'product.template',
            'id': tmpl_data['id'],
            'external_id': str(product.id),
            'attribite_values': {
                'external_data': [dict(x) for x in self._parse_attributes(product, True)],
                'existing_ids': [
                    y['external_id'] for x in tmpl_data['products'] for y in x['attribute_values']
                ],
            },
        }]

        for variant in product.variants:
            for data in tmpl_data['products']:
                if getattr(variant, data['reference_api_field']) == data['reference']:

                    mappings.append({
                        'model': 'product.product',
                        'id': data['id'],
                        'external_id': self._build_product_external_code(
                            product.id,
                            variant.id,
                        ),
                    })

        return mappings

    @add_dynamic_kwargs
    def _find_product_by_references(self, product_refs, **kw):
        products = list()
        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name

        for ref in product_refs:
            result = self._fetch_product_by_ref(variant_reference, ref)
            products.append(result)

        return products

    def _fetch_product_by_ref(self, ecommerce_ref, ref):

        def truncate(item):
            if not item or not isinstance(item, str):
                return False
            return item.rsplit('/', maxsplit=1)[-1]

        node = self._graphql.get_product_id_by_reference(ecommerce_ref, ref)

        variant_id = node.get('id')
        product_id = node.get('product', {}).get('id')

        return truncate(product_id), truncate(variant_id)

    def _parse_attributes(self, product, parse_values=False):
        container = defaultdict(set)

        for option in product.options:
            container[option.name].update(set(option.values))

        if parse_values:
            value_set = set()
            for k, vals in container.items():
                for val in vals:
                    attribute_data = (
                        ('id', format_attr_value_code(k, val)),
                        ('id_group', format_attr_code(k)),
                        ('id_group_name', k),
                        ('name', val),
                    )
                    value_set.add(attribute_data)
            return value_set

        return set([(('id', format_attr_code(x)), ('name', x)) for x in container.keys()])

    def _get_url_pattern(self, wrap_li=True):
        pattern = f'<a href="{self.admin_url}/products/%s/variants/%s" target="_blank">%s</a>'
        if wrap_li:
            return f'<li>{pattern}</li>'
        return pattern

    def _prepare_url_args(self, record):
        if record.parent_id:
            return (record.parent_id, record.id, record.format_name)
        return (record.id, record.id, record.format_name)

    def _convert_to_html(self, id_list):
        pattern = self._get_url_pattern()
        arg_list = [self._prepare_url_args(x) for x in id_list]
        return ''.join([pattern % args for args in arg_list])

    @staticmethod
    def _parse_variant_id(external_id):
        if not external_id or not isinstance(external_id, str):
            return False
        return int(external_id.split('-')[-1])

    @staticmethod
    def _get_option_keys():
        return 'option1', 'option2', 'option3'

    @staticmethod
    def _parse_default_address(address):
        names = [
            # First of last name can be null in Shopify
            (address.get('first_name') or '').strip(),
            (address.get('last_name') or '').strip(),
        ]
        vals = {
            'id': '',
            'email': address.get('email') or '',
            'phone': address.get('phone') or '',
            'person_name': ' '.join(filter(None, names)),
        }
        return vals

    def _parse_customer(self, customer):
        vals = self._parse_default_address(customer)
        vals['id'] = str(customer['id'])
        return vals

    def _parse_address(self, customer, address):
        vals = self._parse_default_address(customer)
        vals.update({
            'phone': address.get('phone') or '',
            'person_name': address.get('name') or '',
            'company_name': address.get('company') or '',
            'street': address.get('address1') or '',
            'street2': address.get('address2') or '',
            'city': address.get('city') or '',
            'country_code': address.get('country_code') or '',
            'state_code': address.get('province_code') or '',
        })

        if address.get('zip'):
            vals['zip'] = address.get('zip')

        return vals

    @add_dynamic_kwargs
    def _get_since_file_for_order(self, **kw):
        env = self._get_env(kw)
        files = env['sale.integration.input.file'].search([
            ('si_id', '=', self._integration_id),
        ])
        files_sorted = files.sorted(key=lambda x: int(x.name))
        last_dtaft = files_sorted.filtered(lambda x: not x.order_id)[:1]

        if not last_dtaft:
            return files_sorted[-1:]

        files_sorted = files_sorted.filtered(lambda x: x.id < last_dtaft.id)
        return files_sorted[-1:]

    @staticmethod
    def _format_tax(tax, is_tax_included):
        """Related to _get_or_create_spf_tax() method on 'account.tax'."""
        rate = str(round(tax['rate'] * 100, 2))
        tax_option = ('excluded', 'included')[is_tax_included]
        return f'{tax["title"]} {rate}% [{tax_option}]'

    def get_weight_uom_for_converter(self):
        if not self._weight_uom:
            raise UserError(_(
                'Sale Integration setting "Shopify weight unit" is not specified. '
                'Please, deactivate and then activate Sale Integration to populate it'))

        return self._weight_uom

    def get_weight_uoms(self):
        if self._weight_uom:
            return [self._weight_uom]
        return []

    def _default_product_domain(self):
        return self.get_settings_value('import_products_filter') or dict()

    def _default_order_domain(self):
        domain = dict()
        status = self.get_settings_value('receive_order_statuses')
        if status:
            domain['status'] = status

        financial_status = self.get_settings_value('receive_order_financial_statuses')
        if financial_status:
            domain['financial_status'] = financial_status

        fulfillment_status = self.get_settings_value('receive_order_fulfillment_statuses')
        if fulfillment_status:
            status_list = fulfillment_status.split(',')
            fulfilled = ShopifyOrderStatus.STATUS_FULFILLED

            if fulfilled in status_list:  # Change the `fulfilled` value to the 'shipped' value
                status_list.remove(fulfilled)
                status_list.append(ShopifyOrderStatus.SPECIAL_STATUS_SHIPPED)
                fulfillment_status = ','.join(status_list)

            domain['fulfillment_status'] = fulfillment_status

        return domain

    def _get_shopify_statuses(self):
        return ShopifyOrderStatus.all_statuses()

    def order_limit_value(self):
        return SHOPIFY_FETCH_LIMIT

    def get_customer_metafields_by_id(self, customer_id):
        metafield_data = self._graphql.get_customer_metafields_by_id(customer_id)
        return [x['node'] for x in metafield_data]

    def get_order_metafields_by_id(self, order_id):
        metafield_data = self._graphql.get_order_metafields_by_id(order_id)
        return [x['node'] for x in metafield_data]

    def get_metafields(self, entity_name):
        metafields = self._graphql.get_metafields(entity_name)
        return [x['node'] for x in metafields]

    def _serialize_fulfillment(self, data):
        return dict(
            name=data['name'],
            external_status=data['status'],
            external_str_id=str(data['id']),
            tracking_number=', '.join(data['tracking_numbers'] or []),
            tracking_company=str(data['tracking_company'] or ''),
            external_location_id=str(data.get('location_id') or ''),
            lines=[self._serialize_fulfillment_line(x) for x in data['line_items']],
        )

    def _serialize_fulfillment_line(self, data):
        return dict(
            external_str_id=str(data['id']),
            quantity=int(data['quantity'] or 0),
            external_reference=str(data['sku'] or ''),
            fulfillable_quantity=int(data['fulfillable_quantity'] or 0),
            code=self._build_product_external_code(data['product_id'], data['variant_id']),
        )

    @check_scope('read_publications')
    def get_sale_channels(self):
        _logger.info('Shopify: get_sale_channels()')

        sale_channels = self._graphql.get_sale_channels()
        return [x['node'] for x in sale_channels]
