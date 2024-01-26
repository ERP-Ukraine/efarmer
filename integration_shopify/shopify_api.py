# See LICENSE file for full copyright and licensing details.

import base64
import logging
from itertools import chain
from collections import defaultdict

import requests
from dateutil import parser

from odoo import _
from odoo.addons.integration.api.abstract_apiclient import AbsApiClient
from odoo.addons.integration.models.fields.common_fields import GENERAL_GROUP
from odoo.addons.integration.tools import not_implemented, TemplateHub, add_dynamic_kwargs
from odoo.exceptions import UserError, ValidationError

from .shopify import Client, check_scope
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
    ORDER_RISK,
)
from .shopify.shopify_client import METAFIELD, LOCATION  # noqa
from .wizard.configuration_wizard_shopify import ShopifyOrderStatus


SHOPIFY = 'shopify'
PAYMENT_NOT_DEFINED = 'Not_Defined'

TXN_SALE = 'sale'
TXN_VOID = 'void'
TXN_AUTH = 'authorization'
TXN_CAPTURE = 'capture'
TXN_STATUS_SUCCESS = 'success'
TXN_STATUS_PENDING = 'pending'
TXN_SOURCE_EXTERNAL = 'external'

SHOPIFY_ATTRIBUTE_PREF = 'shopify-attribute-'
SHOPIFY_ATTRIBUTE_VALUE_PREF = 'shopify-attribute-value-'
SHOPIFY_SHIPPING_PREF = 'shopify-shipping-'
SHOPIFY_PAYMENT_PREF = 'shopify-payment-'
METAFIELDS_NAME = 'metafields'

_logger = logging.getLogger(__name__)


class ShopifyAPIClient(AbsApiClient):

    settings_fields = (
        ('url', 'Shop URL', ''),
        ('version', 'API Version', ''),
        ('key', 'Admin API access token', ''),
        ('secret_key', 'API Secret Key', '', False, True),
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
    )

    def __init__(self, settings):
        super().__init__(settings)

        self._client = Client(settings)

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

    def execute_graphql(self, query):
        return self._client._execute_graphql(query)

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
            variant_external_id = variant['external_id']
            shopify_variant_id = self._parse_variant_id(variant_external_id)
            if shopify_variant_id:
                shopify_variant = self.fetch_one(VARIANT, shopify_variant_id)

                if shopify_variant.is_new():
                    mappings_to_delete.append({
                        'model': 'product.product',
                        'external_id': variant_external_id,
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

        ref_field = integration._get_product_reference_name()
        ecommerce_ref_variant = integration._variant_field_name_to_ecommerce_name(ref_field)

        product_refs = [x['fields'].get(ecommerce_ref_variant) for x in variants]

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
            reference = getattr(combination, ecommerce_ref_variant)

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
                filter(lambda x: x['fields'].get(ecommerce_ref_variant) == reference, variants)
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

                attribute_value_id = self._format_attr_value_code(key, value)
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
        existing_webhooks = self.fetch_multi(WEBHOOK)
        for record in existing_webhooks:
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

        product = self.fetch_one(TEMPLATE, img_data['template']['id'])

        if product.is_new():
            return None

        for image in product.images:
            self.destroy(image)

        image_list = list()

        # Create product image
        if img_data['template']['default']:
            variant_ids = [
                self._parse_variant_id(var['id']) for var in img_data['products'] if var['id']
            ]
            img = self._create_image(img_data['template']['default']['data'], variant_ids)
            image_list.append(img)

        for extra_image in img_data['template']['extra']:
            img = self._create_image(extra_image['data'], [])
            image_list.append(img)

        # Create variant images
        for variant in img_data['products']:
            variant_id = self._parse_variant_id(variant['id'])
            shopify_variant = self.fetch_one(VARIANT, variant_id)

            if shopify_variant.is_new():
                continue

            if variant['default']:
                img = self._create_image(variant['default']['data'], [shopify_variant.id])
                image_list.append(img)

            for extra_image in variant['extra']:
                img = self._create_image(extra_image['data'], [shopify_variant.id])
                image_list.append(img)

        # Attach images to product
        self.refresh(product)
        product.images = image_list
        result = self.save(product)

        return result

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
        'write_orders',
        'write_fulfillments',
        'write_merchant_managed_fulfillment_orders',
    )
    def export_tracking(self, sale_order_id, tracking_data_list):
        _logger.info('Shopify: export_tracking()')

        result_list = []
        order = self.fetch_one(ORDER, sale_order_id)
        if order.is_new():
            raise UserError(
                _('Order with id "%s" does not exist in Shopify') % sale_order_id
            )

        def order_fulfilled(order):
            return order.fulfillment_status == 'fulfilled'

        if order_fulfilled(order):
            raise UserError(_('Order %s already fulfilled.', sale_order_id))

        fulfilled_order_list = self.fetch_multi(
            FULFILLMENT_ORDER,
            params={
                'order_id': sale_order_id,
            },
        )
        fulfilled_order_list = [x for x in fulfilled_order_list if x.status != 'closed']

        if len(fulfilled_order_list) > 1:
            raise ShopifyApiException(_(
                'Multiple Fulfilment Orders found for Shopify Order with ID %s. '
                'Please, contact us at support@ventor.tech to discuss your case, '
                'so we can fix that issue. In your email, please, share with us (1) URL to your '
                'Shopify Instance in format xxx.myshopify.com (2) "Admin API access token", '
                'and (3) Shopify Order ID above. For sharing this secret information, please, '
                'use https://share.ventor.tech/ so your information is not shared via email.'
            ) % sale_order_id)

        fulfilled_order = fulfilled_order_list and fulfilled_order_list[0]
        if not fulfilled_order:
            raise ShopifyApiException(_(
                'Shopify Fulfilled order not found for Shopify Order with ID %s. '
                'Please, contact us at support@ventor.tech to discuss your case, so we can fix '
                'that issue. In your email, please, share with us (1) URL to your Shopify Instance '
                'in format xxx.myshopify.com (2) "Admin API access token", and (3) '
                'Shopify Order ID above. For sharing this secret information, please, '
                'use https://share.ventor.tech/ so your information is not shared via email.'
            ) % sale_order_id)

        fulfilled_line_items_dict = {
            str(x.line_item_id): x for x in fulfilled_order.line_items
        }

        for tracking_data in tracking_data_list:
            fulfillment = self.model_init(FULFILLMENT)

            fulfillment_order_line_items = list()

            for line in tracking_data['lines']:
                fulfilled_line = fulfilled_line_items_dict.get(line['id'])
                if not fulfilled_line:
                    continue

                required_qty = fulfilled_line.fulfillable_quantity
                if not required_qty:
                    continue

                odoo_qty = int(line['qty'])
                export_qty = odoo_qty if (odoo_qty <= required_qty) else required_qty

                fulfillment_order_line_items.append({
                    'id': fulfilled_line.id,
                    'quantity': export_qty,
                })

            line_items_by_fulfillment_order = [{
                'fulfillment_order_id': fulfilled_order.id,
                'fulfillment_order_line_items': fulfillment_order_line_items,
            }]
            tracking_info = {
                'number': tracking_data['tracking'] or '',
                'company': tracking_data['carrier'] if 'carrier' in tracking_data else '',
            }

            fulfillment.notify_customer = True
            fulfillment.tracking_info = tracking_info
            fulfillment.line_items_by_fulfillment_order = line_items_by_fulfillment_order

            result = self.save(fulfillment)
            result_list.append(result)

            self.refresh(order)
            if order_fulfilled(order):
                # TODO: We have tracking data from `tracking_data_list`
                # However the order was `partially fulfilled` and we need to skip next iteration
                break

        return result_list

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
        if not order.id or order.financial_status == 'paid':
            return True, dict()

        if order.financial_status == 'partially_paid':  # TODO
            raise ValidationError(
                _('We do not support yet marking as paid for "Partial Paid" orders')
            )

        params = dict(order_id=order_id)
        txn_list = self.fetch_multi(TRANSACTION, params=params)
        except_ids = [
            x.parent_id for x in txn_list if x.kind == TXN_VOID and x.status == TXN_STATUS_SUCCESS
        ]
        txn_list = [
            x for x in txn_list if x.kind in (TXN_AUTH, TXN_SALE)
            and x.status in (TXN_STATUS_PENDING, TXN_STATUS_SUCCESS)
            and x.id not in except_ids
        ]

        parent = txn_list[-1] if txn_list else False
        txn = self.model_init(TRANSACTION, prefix_options=params)

        if not parent:
            txn.kind = TXN_SALE
            txn.source = TXN_SOURCE_EXTERNAL
            txn.amount = amount
            txn.currency = currency

        elif parent.kind == TXN_SALE:
            if parent.status == TXN_STATUS_PENDING:
                txn.kind = TXN_CAPTURE  # TODO: make sure that `parent.amount == amount`
                txn.parent_id = parent.id
            else:
                txn.kind = TXN_SALE
                txn.source = TXN_SOURCE_EXTERNAL
                txn.amount = amount
                txn.currency = currency

        else:
            if parent.status == TXN_STATUS_PENDING:  # TODO: do the math how to perform
                raise ValidationError(               # pending parent transaction without raising
                    _('Awaiting for the transaction: %s') % parent.to_dict()
                )

            txn.kind = TXN_CAPTURE
            txn.parent_id = parent.id
            txn.amount = amount
            txn.currency = currency

        result = self.save(txn)
        return result, txn.to_dict()

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

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def receive_orders(self, **kw):
        _logger.info('Shopify: receive_orders()')

        kwargs = self.order_fetch_kwargs()(**kw)
        orders = self.fetch_multi(ORDER, **kwargs)

        result = list()
        for order in orders:
            vals = dict(
                id=str(order.id),
                data=order.to_dict(),
                updated_at=order.updated_at,
                created_at=order.created_at,
            )
            result.append(vals)

        return result

    @check_scope('read_orders')
    def receive_order(self, order_id):
        input_file = dict()
        order = self.fetch_one(ORDER, order_id)
        if order.is_new():
            return input_file

        input_file['id'] = order_id
        input_file['data'] = order.to_dict()
        return input_file

    @add_dynamic_kwargs
    def parse_order(self, input_file, **kw):
        _logger.info('Shopify: parse_order() from input file.')
        integration = self._get_integration(kw)
        use_customer_currency = integration.use_customer_currency

        external_order_id = str(input_file['id'])

        order_lines = input_file['line_items']
        tax_is_included = input_file['taxes_included']
        presentment_currency = input_file['presentment_currency']

        parsed_lines = [
            self._parse_order_line(x, tax_is_included, presentment_currency, use_customer_currency)
            for x in order_lines
        ]

        delivery_data = self._parse_delivery_data(
            input_file, tax_is_included, presentment_currency, use_customer_currency)

        payment_method = self._parse_payment_code(input_file)

        order_risks = self.fetch_order_risks(external_order_id)
        order_txns = self.fetch_order_payments(external_order_id)

        total_price = float(input_file['total_price'])
        if use_customer_currency:
            total_price = self._get_price_in_customer_currency(
                total_price, input_file['total_price_set'], presentment_currency)

        order_vals = {
            'id': external_order_id,
            'ref': input_file['name'],
            'date_order': input_file['created_at'],
            'lines': parsed_lines,
            'currency': presentment_currency if use_customer_currency else input_file['currency'],
            'payment_method': payment_method,
            'amount_total': total_price,
            'delivery_data': delivery_data,
            'discount_data': dict(),
            'gift_data': dict(),
            'current_order_state': '',
            'integration_workflow_states': self._parse_workflow_states(input_file),
            'order_risks': order_risks,
            'order_transactions': order_txns,
            'external_tags': self._parse_tags(input_file),
            'is_cancelled': True if input_file.get('cancel_reason', False) else False,
        }

        customer = input_file.get('customer')

        if customer:
            order_vals['customer'] = self._parse_customer(
                customer,
            )
            order_vals['shipping'] = self._parse_address(
                customer,
                input_file.get('shipping_address', {}) or {},
            )
            order_vals['billing'] = self._parse_address(
                customer,
                input_file.get('billing_address', {}) or {},
            )

        return order_vals

    def fetch_order_risks(self, external_order_id):
        records = self.fetch_multi(ORDER_RISK, params={'order_id': external_order_id})
        if not records:
            return list()
        return [x.to_dict() for x in records]

    def fetch_order_payments(self, external_order_id):
        records = self.fetch_multi(TRANSACTION, params={'order_id': external_order_id})
        if not records:
            return list()

        f_records = filter(
            lambda x: x.status == 'success' and x.kind in ('capture', 'sale'), records
        )
        return [x.to_dict() for x in f_records]

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def get_delivery_methods(self, **kw):
        _logger.info('Shopify: get_delivery_methods()')

        integration = self._get_integration(kw)
        integration.integrationApiReceiveOrders()
        env = self._get_env(kw)
        input_files = env['sale.integration.input.file'].search([
            ('si_id', '=', self._integration_id),
        ])

        # Parse taxes derectly from input-files
        shipping_methods = set()
        for input_file in input_files:
            order = input_file.to_dict()

            for line in order.get('shipping_lines', []):
                title = line.get('title')
                code = line.get('code')
                ext_code = self._format_delivery_code(title, code)
                if not ext_code:
                    continue
                shipping_methods.add(
                    (('id', ext_code), ('name', (title or code)))
                )

        return [dict(x) for x in shipping_methods]

    def get_single_tax(self, tax_id):
        _logger.info('Shopify: get_single_tax(). No implemented')
        return dict()

    @add_dynamic_kwargs
    def get_taxes(self, **kw):
        _logger.info('Shopify: get_taxes()')

        integration = self._get_integration(kw)
        integration.integrationApiReceiveOrders()
        env = self._get_env(kw)
        input_files = env['sale.integration.input.file'].search([
            ('si_id', '=', self._integration_id),
        ])

        # Parse taxes derectly from input-files
        tax_set = set()
        to_external_tax = integration._fetch_external_tax

        for input_file in input_files:
            order = input_file.to_dict()
            tax_included = order.get('taxes_included')

            line_tax_list = [
                self._format_tax(tax, tax_included)
                for line in order['line_items'] for tax in line['tax_lines']
            ]
            carrier = order['shipping_lines'] and order['shipping_lines'][0] or dict()
            carrier_tax_lines = carrier and carrier['tax_lines'] or list()

            carrier_tax_list = [
                self._format_tax(tax, tax_included) for tax in carrier_tax_lines
            ]
            tax_set.update(set(line_tax_list + carrier_tax_list))

        return [to_external_tax(x) for x in tax_set]

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def get_payment_methods(self, **kw):
        _logger.info('Shopify: get_payment_methods()')

        integration = self._get_integration(kw)
        integration.integrationApiReceiveOrders()
        env = self._get_env(kw)
        input_files = env['sale.integration.input.file'].search([
            ('si_id', '=', self._integration_id),
        ])

        empty_code = self._format_payment_code(None)
        payment_methods = {(('id', empty_code), ('name', empty_code))}

        for input_file in input_files:
            order = input_file.to_dict()

            for name in order.get('payment_gateway_names', []):
                if not name:
                    continue

                ext_code = self._format_payment_code(name)
                payment_methods.add(
                    (('id', ext_code), ('name', name))
                )

        return [dict(x) for x in payment_methods]

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
        """
            {
                "data": {
                    "shop":{
                        "productTags": {
                            "edges": [
                                {
                                    "node": "tag_name"
                                }
                            ]
                        }
                    }
                },
                "extensions": {
                    "cost": {
                        "requestedQueryCost": 22,
                        "actualQueryCost": 4,
                        "throttleStatus": {
                            "maximumAvailable": 1000.0,
                            "currentlyAvailable": 996,
                            "restoreRate": 50.0
                        }
                    }
                }
            }
        """
        _logger.info('Shopify: get_feature_values()')
        query = """
            {
                shop {
                    productTags(first: 250) {
                        edges {
                            node
                        }
                    }
                }
            }
        """
        response = self.execute_graphql(query)
        tags = response.get('data', {}).get('shop', {}).get('productTags', {}).get('edges', [])

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
        ref_field = integration._get_product_reference_name()
        barcode_field = integration._get_product_barcode_name()

        ecommerce_ref_variant = integration._variant_field_name_to_ecommerce_name(ref_field)
        ecommerce_barcode_variant = integration._variant_field_name_to_ecommerce_name(barcode_field)

        def parse_variant(template, variant):
            attribute_value_tmpl_ids = self._attribute_value_from_template(template)
            attribute_var_ids = self._attribute_value_from_variant(
                variant,
                attribute_value_tmpl_ids,
            )

            return {
                'id': self._build_product_external_code(template.id, variant.id),
                'name': template.title,
                'external_reference': getattr(variant, ecommerce_ref_variant) or None,
                'barcode': getattr(variant, ecommerce_barcode_variant) or None,
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
                barcode = getattr(variants[0], ecommerce_barcode_variant) or None
                external_ref = getattr(variants[0], ecommerce_ref_variant) or None

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

            if variant.image_id:
                images_hub['variants'][variant_id] = [str(variant.image_id)]

        return product, variants, list(), images_hub  # TODO: convert `product` to dict

    def _attribute_value_from_template(self, product):
        attribute_value_tmpl_ids = list()
        for opt in product.options:
            for value in opt.values:
                attribute_value_tmpl_ids.append(
                    self._format_attr_value_code(opt.name, value)
                )
        return attribute_value_tmpl_ids

    def _attribute_value_from_variant(self, variant, attribute_value_tmpl_ids):
        keys = self._get_option_keys()
        options = [
            getattr(variant, key) for key in keys if getattr(variant, key)
        ]
        attribute_var_ids = list()
        for option in options:
            for attr in attribute_value_tmpl_ids:
                __, option_value = self._parse_attr_value_code(attr)
                if option == option_value:
                    attribute_var_ids.append(attr)

        return attribute_var_ids

    @not_implemented
    def get_products_for_accessories(self):
        pass

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
        ref_field = integration._get_product_reference_name()
        barcode_field = integration._get_product_barcode_name()
        ecommerce_ref_variant = integration._variant_field_name_to_ecommerce_name(ref_field)
        ecommerce_barcode_variant = integration._variant_field_name_to_ecommerce_name(barcode_field)

        def serialize_template(t):

            def serialize_variant(v):
                return {
                    'id': str(v['id']),
                    'name': v['title'],
                    'barcode': v.get(ecommerce_barcode_variant) or '',
                    'ref': v.get(ecommerce_ref_variant) or '',
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

    def _set_base_values(self, spf_lib_model, data):
        for field, value in data.items():
            setattr(spf_lib_model, field, value)

    def _create_image(self, data, variant_ids=False):
        image = self.model_init(IMAGE)
        image.variant_ids = variant_ids or []
        image.attach_image(base64.b64decode(data))
        return image

    def _update_variants(self, product, variant_list):
        # Drop variants if necessary
        odoo_external_ids = [
            self._parse_variant_id(var['external_id']) for var in variant_list if var['external_id']
        ]
        for variant in product.variants:
            if variant.id not in odoo_external_ids:
                self.destroy(variant)

        # Update variants
        self.refresh(product)
        self._attach_variants(product, variant_list)

    def _build_variant(self, data):
        variant_id = data['external_id'] and self._parse_variant_id(data['external_id'])
        variant = self.fetch_one(VARIANT, variant_id)

        self._set_base_values(variant, data['fields'])
        variant.inventory_management = SHOPIFY  # TODO: need to think

        keys = self._get_option_keys()
        values = [attr['value'] for attr in data['attribute_values']]

        for key, value in zip(keys, values):
            setattr(variant, key, value)

        return variant

    def _attach_variants(self, product, variant_list):
        options_dict = defaultdict(list)
        product.variants = list()

        for variant in variant_list:
            variant['_options'] = set()
            product.variants.append(
                self._build_variant(variant)
            )
            for attr in variant['attribute_values']:
                option = attr['value']

                variant['_options'].add(option)
                options_dict[attr['key']].append(option)

        if options_dict:  # avoid 'could not update options to []' shopify api error
            product.options = [
                {'name': k, 'values': list(v)} for k, v in options_dict.items()
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

        keys = self._get_option_keys()
        for shopify_variant in product.variants:
            variant = None
            options = {
                getattr(shopify_variant, key) for key in keys if getattr(shopify_variant, key)
            }
            for item in tmpl_data['products']:
                if item.get('_options', set()) == options:
                    variant = item
                    break

            if variant:
                external_id = self._build_product_external_code(product.id, shopify_variant.id)
                mappings.append({
                    'model': 'product.product',
                    'id': variant['id'],
                    'external_id': external_id,
                })

        return mappings

    @add_dynamic_kwargs
    def _find_product_by_references(self, product_refs, **kw):
        integration = self._get_integration(kw)
        ref_field = integration._get_product_reference_name()
        ecommerce_ref_variant = integration._variant_field_name_to_ecommerce_name(ref_field)

        products = list()
        for ref in product_refs:
            result = self._fetch_product_by_ref(ecommerce_ref_variant, ref)
            products.append(result)
        return products

    @staticmethod
    def _product_variant_graph(field_name, field_value):
        return """
            {
                productVariants(first: 1, query: "%s:%s") {
                    edges
                    {
                        node {
                            id
                            %s
                            product {
                                id
                            }
                        }
                    }
                }
            }
        """ % (field_name, field_value, field_name)

    def _fetch_product_by_ref(self, ecommerce_ref, ref):
        """
            {
                "data": {
                    "productVariants": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/ProductVariant/43274068099312",
                                    "sku": "cp-1",
                                    "product": {
                                        "id": "gid://shopify/Product/8058970145008"
                                    }
                                }
                            }
                        ]
                    }
                },
                "extensions": {
                    "cost": {
                        "requestedQueryCost": 22,
                        "actualQueryCost": 4,
                        "throttleStatus": {
                            "maximumAvailable": 1000.0,
                            "currentlyAvailable": 996,
                            "restoreRate": 50.0
                        }
                    }
                }
            }
        """

        def truncate(item):
            if not item or not isinstance(item, str):
                return False
            return item.rsplit('/', maxsplit=1)[-1]

        query = self._product_variant_graph(ecommerce_ref, ref)
        result = self.execute_graphql(query)

        edges = result['data']['productVariants']['edges']
        node = edges and edges[0]['node'] or dict()

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
                        ('id', self._format_attr_value_code(k, val)),
                        ('id_group', self._format_attr_code(k)),
                        ('id_group_name', k),
                        ('name', val),
                    )
                    value_set.add(attribute_data)
            return value_set

        return set([(('id', self._format_attr_code(x)), ('name', x)) for x in container.keys()])

    @staticmethod
    def _parse_workflow_states(data):
        """
        Order of the `financial_status` (1)
        and 'fulfillment_status' (2) matters
        """

        fulfillment_status = data['fulfillment_status']
        if not fulfillment_status:
            # TODO: seems here we need to add also the status `unshipped`
            # due to the `null` value relates to `unshipped` status as well
            fulfillment_status = ShopifyOrderStatus.STATUS_UNFULFILLED

        return [
            data['financial_status'],
            fulfillment_status,
        ]

    @staticmethod
    def _parse_payment_code(data):
        pay_code_list = data.get('payment_gateway_names', [])
        name = pay_code_list and pay_code_list[0] or None
        return ShopifyAPIClient._format_payment_code(name)

    @staticmethod
    def _parse_tags(data):
        tag_string = data.get('tags', '')
        if not tag_string:
            return list()
        return list(set(x.strip() for x in tag_string.split(',')))

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
    def _parse_attr_code(name):
        return name.replace(SHOPIFY_ATTRIBUTE_PREF, '')

    @staticmethod
    def _parse_attr_value_code(complex_name):
        pure_name = complex_name.replace(SHOPIFY_ATTRIBUTE_VALUE_PREF, '')
        option_name, option_value = pure_name.split('-', maxsplit=1)
        return option_name, option_value

    @staticmethod
    def _format_delivery_code(*args):
        if not any(args):
            return str()
        splitted_args = sum(map(lambda x: x.split(), args), [])
        name = ''.join([arg.title() for arg in splitted_args])
        return f'{SHOPIFY_SHIPPING_PREF}{name}'

    @staticmethod
    def _format_attr_code(name):
        return f'{SHOPIFY_ATTRIBUTE_PREF}{name}'

    @staticmethod
    def _format_attr_value_code(option_name, option_value):
        return f'{SHOPIFY_ATTRIBUTE_VALUE_PREF}{option_name}-{option_value}'

    @staticmethod
    def _format_payment_code(name):
        if name:
            return f'{SHOPIFY_PAYMENT_PREF}{name}'
        return f'{SHOPIFY_PAYMENT_PREF}{PAYMENT_NOT_DEFINED}'

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
    def _format_tax(tax, tax_is_included):
        """Related to _get_or_create_spf_tax() method on 'account.tax'."""
        rate = str(round(tax['rate'] * 100, 2))
        tax_option = ('excluded', 'included')[tax_is_included]
        _tax_format = f'{tax["title"]} {rate}% [{tax_option}]'
        return _tax_format

    def _parse_order_line(
            self, line, tax_is_included, presentment_currency, use_customer_currency):
        price = float(line['price'])
        if use_customer_currency:
            price = self._get_price_in_customer_currency(
                price, line['price_set'], presentment_currency)

        quantity = line['quantity']

        external_id = self._build_product_external_code(
            line['product_id'],
            line['variant_id'],
        )

        tax_list = list()
        if line['taxable']:
            tax_list = [
                self._format_tax(tax, tax_is_included) for tax in line['tax_lines']
            ]

        line_vals = {
            'id': str(line['id']),
            'product_id': external_id,
            'price_unit': price,
            'product_uom_qty': quantity,
            'price_unit_tax_incl': tax_is_included and price or float(),
            'taxes': tax_list,
        }

        # Calculate total discount if any
        if line.get('discount_allocations'):
            line_vals['discount'] = self._calculate_discount(
                line.get('discount_allocations'), presentment_currency, use_customer_currency)

        return line_vals

    def _parse_delivery_data(self, input_file, tax_is_included, presentment_currency, use_customer_currency):  # NOQA
        """
        Parse original input file to get required delivery data
        """
        carrier = input_file['shipping_lines'] and input_file['shipping_lines'][0] or dict()
        carrier_title = carrier.get('title', '')
        carrier_code = carrier.get('code', '')

        carrier_data = dict()
        if carrier_title and carrier_code:
            carrier_data['name'] = carrier_title
            carrier_data['id'] = self._format_delivery_code(carrier_title, carrier_code)

        tax_list = [
            self._format_tax(tax, tax_is_included) for tax in carrier.get('tax_lines', {})
        ]

        shipping_cost = carrier and float(carrier['price']) or float()
        if use_customer_currency and carrier:
            shipping_cost = self._get_price_in_customer_currency(
                shipping_cost, carrier['price_set'], presentment_currency)

        delivery_notes = input_file.get('note') or ''

        # Calculate total discount if any
        discount = None
        if carrier.get('discount_allocations'):
            discount = self._calculate_discount(
                carrier.get('discount_allocations'), presentment_currency, use_customer_currency)

        return {
            'carrier': carrier_data,
            'shipping_cost': shipping_cost,
            'taxes': tax_list,
            'delivery_notes': delivery_notes,
            'discount': discount,
        }

    def _calculate_discount(self, discount_allocations_data, presentment_currency, use_customer_currency):  # NOQA
        total_discount = 0.0

        for discount_allocation in discount_allocations_data:
            discount_amount = float(discount_allocation.get('amount'))
            if use_customer_currency:
                discount_amount = self._get_price_in_customer_currency(
                    discount_amount,
                    discount_allocation.get('amount_set'),
                    presentment_currency,
                )
            total_discount += discount_amount

        return total_discount

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

    def _get_price_in_customer_currency(self, price, price_set, presentment_currency):
        """
        Return price based on the customer's currency.
        """
        shop_money = price_set.get('shop_money', {})
        presentment_money = price_set.get('presentment_money', {})

        if float(shop_money['amount']) > 0.0 and \
                shop_money['currency_code'] == presentment_currency:
            price = shop_money['amount']
        elif float(presentment_money['amount']) > 0.0 and \
                presentment_money['currency_code'] == presentment_currency:
            price = presentment_money['amount']
        return float(price)

    def order_limit_value(self):
        return 250
