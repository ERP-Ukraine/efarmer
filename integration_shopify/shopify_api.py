# See LICENSE file for full copyright and licensing details.

import base64
import itertools
import logging
import math

from time import sleep
from copy import deepcopy
from collections import defaultdict
from datetime import datetime  # NOQA
from dateutil import parser
from typing import List, Dict

import requests

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.integration.api.abstract_apiclient import AbsApiClient
from odoo.addons.integration.tools import (
    not_implemented,
    add_dynamic_kwargs,
    TemplateHub,
    ExternalImage,
    ProductType,
    flatten_recursive,
)

from .shopify.exceptions import ShopifyApiError
from .tools import CheckScope as check_scope, lists_are_equal
from .shopify.shopify_graphql import ShopifyGraphQL

from .shopify.resources.order_status import OrderStatus
from .shopify.resources.order_display_financial_status import OrderDisplayFinancialStatus
from .shopify.resources.order_display_fulfillment_status import OrderDisplayFulfillmentStatus


SHOPIFY = 'shopify'
METAFIELDS_NAME = 'metafields'

REQUIRED_SCOPES = (
    'read_locales',
    'read_markets',
    'read_customers',
    'read_products',
    'write_products',
    'read_orders',
    'write_orders',
    'read_locations',
    'read_shipping',
    'read_inventory',
    'write_inventory',
    'write_fulfillments',
    'read_fulfillments',
    'read_metaobjects',
    'write_metaobjects',
    'read_metaobject_definitions',
    'read_merchant_managed_fulfillment_orders',
    'write_merchant_managed_fulfillment_orders',
    'read_third_party_fulfillment_orders',
    'write_third_party_fulfillment_orders',
    'read_publications',
    'write_publications',
    'read_translations',
    'write_translations',
    'read_files',
    'write_files',
    'read_shopify_payments_payouts',
)

_logger = logging.getLogger(__name__)


class ShopifyAPIClient(AbsApiClient):

    settings_fields = (
        ('url', 'Shop URL', ''),
        ('key', 'Admin API access token', '', False, True),
        ('client_id', 'Client ID', '', False, True),
        ('secret_key', 'API Secret Key', '', False, True),
        ('use_oauth', 'Use OAuth', 'True', True),
        ('language_id', 'Shop Language Code', ''),
        ('import_products_filter', 'Import Products Filter', '{"status": "active"}', True),
        (
            'receive_order_statuses',
            'Order statuses separated by comma',
            OrderStatus.open.name,
        ),
        (
            'receive_order_financial_statuses',
            'Order financial statuses separated by comma',
            OrderDisplayFinancialStatus.paid.name,
        ),
        (
            'receive_order_fulfillment_statuses',
            'Order fulfillment statuses separated by comma',
            OrderDisplayFulfillmentStatus.fulfilled.name,
        ),
        ('decimal_precision', 'Number of decimal places in the price of the exported product', '2'),
        ('batch_size', 'Number of orders processed in one batch', '1000'),
        ('debug_mode', 'Enable debug mode for the verbose logging of the API requests (0 / 1)', '0', True),
        *AbsApiClient.settings_fields,
    )

    def __init__(self, settings):
        super().__init__(settings)

        self.gql = ShopifyGraphQL(
            settings['fields']['url']['value'],
            settings['fields']['key']['value'],
            settings['graphql_version'],
            settings['debug_mode'],
        )

        self.__shop = self.gql.Shop

    @property
    def _graphql(self):
        _logger.warning('ShopifyAPIClient: the "_graphql" attribute is deprecated, use "gql" instead.')
        return self.gql

    @property
    def shop(self):
        if not self.__shop:
            self.__shop.init()
        return self.__shop

    @property
    def access_scopes(self):
        return self.shop.access_scopes

    @property
    def country_code(self):
        return self.shop.country_code

    @property
    def currency_code(self):
        return self.shop.currency_code

    @property
    def admin_url(self):
        return self.gql.admin_url

    @property
    def primary_locale(self):
        return self.shop.get_primary_locale()

    @property
    def lang(self):
        return self.primary_locale.locale

    @property
    def batch_size(self):
        return int(self.get_settings_value('batch_size'))

    @property
    def primary_location_id(self):
        return self.get_settings_value('primary_location_id')  # TODO

    def get_api_resources(self):
        return

    def get_weight_uom_for_converter(self):
        return self.shop.weight_unit

    def get_weight_uoms(self):
        # The available weight units in Shopify are
        weight_unit = self.gql.WeightUnit

        return [
            weight_unit.g.name,
            weight_unit.kg.name,
            weight_unit.lb.name,
            weight_unit.oz.name,
        ]

    def validate_template(self, template_data: dict) -> list:
        _logger.info('Shopify "%s": validate_template()', self._integration_name)
        ext_records_to_delete = []

        # (1) if template with such external id exists?
        external_product_id = template_data['external_id']
        if external_product_id:
            product = self.gql.Product.get_by_pk(external_product_id, raise_if_not_found=False)

            if not product:
                ext_records_to_delete.append({
                    'model': 'product.template',
                    'odoo_external_id': template_data['odoo_external_id'],
                    'external_id': external_product_id,
                })

        # (2) if variant with such external id exists?
        complex_ids = [x['external_id'] for x in template_data['products'] if x['external_id']]
        if not complex_ids:
            return ext_records_to_delete

        external_variant_ids = []
        for complex_id in complex_ids:
            __, external_variant_id = self._parse_product_external_code(complex_id)
            external_variant_ids.append(external_variant_id)

        product_variants = self.gql.ProductVariant.get_by_ids(external_variant_ids)
        actual_variant_ids = [x.id_str for x in product_variants]

        for variant_data in template_data['products']:
            __, external_variant_id = self._parse_product_external_code(variant_data['external_id'])
            if not external_variant_id:
                continue

            if external_variant_id not in actual_variant_ids:
                ext_records_to_delete.append({
                    'model': 'product.product',
                    'odoo_external_id': variant_data['odoo_external_id'],
                    'external_id': external_variant_id.rsplit('/', 1)[-1],
                })

        return ext_records_to_delete

    def find_existing_template(self, template_data: dict):
        _logger.info('Shopify "%s": find_existing_template()', self._integration_name)

        # Now let's validate if there are no duplicated references in Shopify
        products = template_data['products']
        variant_refs = [x['reference'] for x in products]
        reference_api_field = products[0]['reference_api_field']

        # Let's validate if all found products belong to the same product template
        product_variants = self.gql.ProductVariant.get_batch(
            body='id %s product { id }' % reference_api_field,
            filter_params=' OR '.join(f'({reference_api_field}:\\"{ref}\\")' for ref in variant_refs),
        )

        product_ids = [x.product.id_str for x in product_variants]

        # If nothing found, then just return False
        if not product_ids:
            return False

        # If more than one product id found - then we found references,
        # but they all belong to different products and we need to inform user about it
        # So he can fix on Shopify side
        # Because in Odoo it is single product template, and in Shopify - separate
        # product templates. That should not be allowed. Note that after previous check on
        # duplicates most likely it will not be possible, this check is just to be 100% sure
        if len(set(product_ids)) > 1:
            error_message = _(
                'Product reference(s) "%s" were found in multiple Shopify Products: %s. '
                'This is not allowed as in Odoo, these references already belong to a single '
                'product template and its variants. Ensure the structure of products in Shopify '
                'matches the Odoo product template structure.'
            ) % (', '.join(variant_refs), ', '.join(product_ids))
            raise UserError(error_message)

        external_product_id = product_ids[0]

        # Check if products in Odoo has the same amount of variants as in Shopify
        product = self.gql.Product.get_by_pk(external_product_id)
        variants = product.variants
        # counting expected variants excluding "virtual" variant
        # template_variants_count = len([x for x in variants if x['attribute_values']])
        if len(variant_refs) != len(variants):
            raise UserError(_(
                'The number of combinations in Shopify (%d) does not match Odoo (%d). '
                'Check the product with ID %s in Shopify and ensure the combination count matches '
                'the variant count in Odoo (Integration: "%s").'
            ) % (
                len(variants),
                len(variant_refs),
                external_product_id,
                self._integration_name,
            ))

        for variant in variants:
            # Make sure that reference is set on the combination
            reference = getattr(variant, reference_api_field)

            if not reference:
                raise UserError(_(
                    'Product with ID "%s" lacks references for all combinations. '
                    'Add the missing references and retry the export process.'
                ) % external_product_id)

            current_odoo_variant = list(filter(lambda x: x['reference'] == reference, products))

            if not current_odoo_variant:
                raise UserError(_(
                    'No Odoo variant found with reference "%s" matching Shopify product ID %s.'
                ) % (reference, external_product_id))

            attribute_values_from_odoo = list()
            for values in current_odoo_variant[0]['attribute_values']:
                attribute_values_from_odoo.append(
                    variant.format_attr_value_code(values['optionName'], values['name']).lower()
                )

            attribute_values_from_shopify = variant.get_attribute_values(lowercase=True)
            if not (set(attribute_values_from_odoo) == set(attribute_values_from_shopify)):
                raise UserError(_(
                    'Mismatch in attribute values for Shopify variant with reference "%s": '
                    'Shopify values: %s; Odoo values: %s. Products with the same reference '
                    'must have identical attribute combinations in Shopify and Odoo.'
                    ) % (
                        reference,
                        attribute_values_from_shopify,
                        attribute_values_from_odoo,
                    )
                )

        return external_product_id

    def create_webhooks_from_routes(self, routes_dict):
        result = dict()

        for name_tuple, callback_url in routes_dict.items():
            record = self.gql.WebhookSubscription.create(name_tuple[-1], callback_url)
            result[name_tuple] = record.id_str

        return result

    def unlink_existing_webhooks(self, external_ids: list = None):
        if not external_ids:
            return False

        for external_id in external_ids:
            self.gql.WebhookSubscription.delete_by_pk(external_id)

        return True

    @check_scope('write_products')
    def export_template(self, data: dict) -> list:
        _logger.info('Shopify "%s": export_template()', self._integration_name)

        external_id = data['gid']

        if external_id:
            product = self._update_product(external_id, data)
        else:
            product = self._create_product(data)

        mappings = product._serialize_to_mappings(data)

        return mappings

    def _create_product(self, data: dict) -> dict:
        _logger.info('Shopify "%s": _create_product()', self._integration_name)

        # 1. Prepare payload
        payload = {
            **self._prepare_converted_fields(data['fields']),
            'productOptions': data['attribute_values'],
            'variants': [
                {
                    **self._prepare_converted_fields(x['fields']),
                    'optionValues': x['attribute_values'],
                } for x in data['products']
            ],
        }

        product = self.gql.Product

        # 1.1 If no product options, add default "Title" option
        if not payload['productOptions']:
            payload['productOptions'] = [
                {
                    'name': product.ATTRIBUTE_DEFAULT_TITLE,
                    'values': [
                        {
                            'name': product.ATTRIBUTE_DEFAULT_VALUE,
                        },
                    ],
                },
            ]

        # 1.2 If no variant option values, add default "Title" option
        for variant in payload['variants']:
            if not variant['optionValues']:
                variant['optionValues'] = [
                    {
                        'optionName': product.ATTRIBUTE_DEFAULT_TITLE,
                        'name': product.ATTRIBUTE_DEFAULT_VALUE,
                    },
                ]

        return product.create_product_all_in_one(payload)

    def _update_product(self, external_id: str, data: dict) -> dict:
        _logger.info('Shopify "%s": _update_product()', self._integration_name)

        product = self.gql.Product.get_by_pk(external_id)

        # 1. Update product options:
        #     - Delete deprecated options
        #     - Delete deprecated option-values
        #     - Create the brand new options and values
        # Options updating triggers deleting and creating variants according to mutations strategies.
        product._update_options(data['attribute_values'])

        # 2. Try to map serialized products to existing product variants by an attributes set.
        if product.has_only_one_variant:
            if data['variants_count'] == 1:
                variant = product.variants[0]
                data['products'][0]['gid'] = variant.gid
                data['products'][0]['external_id'] = variant.external_id
        else:
            for variant_data in data['products']:
                attribute_values = variant_data['attribute_values']

                if attribute_values:
                    options = [(x['optionName'], x['name']) for x in variant_data['attribute_values']]
                    variant = product._find_suitable_variant_by_options(options)

                    if variant:
                        variant_data.update(
                            gid=variant.gid,
                            external_id=variant.external_id,
                        )

        # 3. Update existing variants by the actual values (productVariantsBulkUpdate).
        variants_data_to_update = []
        for variant_data in filter(lambda x: x['gid'], data['products']):
            values = {
                'id': variant_data['gid'],
                **self._prepare_converted_fields(variant_data['fields']),
            }
            variants_data_to_update.append(values)

        if variants_data_to_update:
            product.bulk_update_variants(variants_data_to_update)
            product.read()

        # 4. Create new variants (productVariantsBulkCreate).
        variants_data_to_create = []
        for variant_data in filter(lambda x: not x['gid'], data['products']):
            values = {
                **self._prepare_converted_fields(variant_data['fields']),
                'optionValues': [],
            }
            for a_values in variant_data['attribute_values']:
                # Assign an optionId instead of optionName for the productVariantsBulkCreate mutation.
                values['optionValues'].append({
                    'name': a_values['name'],
                    'optionId': product._get_option_id_by_name(a_values['optionName']) ,
                })

            variants_data_to_create.append(values)

        if variants_data_to_create:
            product.bulk_create_variants(variants_data_to_create)
            product.read()

        # 5. Update product by actual values (productUpdate).
        values = self._prepare_converted_fields(data['fields'])
        product.update(values)

        # 6. Refresh product
        product.read()

        return product

    @check_scope('write_products', 'read_files', 'write_files')
    def export_template_images(
        self,
        external_template_id: str,
        datacls_list: List[ExternalImage],
        **kw,
    ) -> List[ExternalImage]:
        """
        1. All the product images stores on the template level.
        2. Template cover has property: posotion = 1.
        3. Product variant just have a FK to the image from parent template (variant support only one image).
        """
        _logger.info('Shopify "%s": export_images()', self._integration_name)

        template = self.gql.Product.get_by_pk(external_template_id)

        # 1. Drop old images
        current_ids = [x.code for x in datacls_list if x.code]
        if not current_ids:  # It means a) the first time export; b) all mappings were dropped
            template.delete_product_media()
        else:
            to_delete_ids = [x.gid for x in template.media if x.gid not in current_ids]
            self.gql.MediaImage.delete_batch(to_delete_ids)

        # 1.1 Refresh template
        template.read()

        # 2. Prepare images to create
        variants_append_media = []
        to_create_images = sorted([x for x in datacls_list if x.to_create], key=lambda x: x.checksum)

        # 2.1 Grouping new images by checksum to avoid duplicates
        for checksum, group in itertools.groupby(to_create_images, key=lambda x: x.checksum):
            group = list(group)
            datacls = group[0]

            media_file = self.gql.File.create(
                filename=datacls._get_unique_filename(),
                mimetype=datacls.mimetype,
                binary_data=datacls.b64_ascii,
            )

            # 2.2 Wait for the media-file to be ready
            for __ in range(3):
                if media_file.is_not_ready:
                    sleep(1.6)
                    media_file._read()
                else:
                    break
            else:
                raise ShopifyApiError(_('Media file may not be created: %s') % media_file.to_dict())

            # 2.3 Attach image to product
            media_file.update(template.id)

            for datacls in filter(lambda x: x.is_variant_cover, group):
                variants_append_media.append({
                    'mediaIds': [media_file.media_image_gid],
                    'variantId': self.gql.ProductVariant.create_gid(datacls.variant_code),
                })

            if any(x.is_template_cover for x in group):
                template.set_image_as_cover(media_file.media_image_gid)

            # 2.4 Update datacls with new image data to update Odoo mappings
            datacls_to_update = [x for x in datacls_list if (x.to_assign and x.checksum == checksum)]
            datacls_to_update.extend(group)

            for datacls in datacls_to_update:
                datacls.update(
                    code=media_file.media_image_gid,
                    name=media_file.name,
                    src=media_file.src,
                )

        # 3. Reassign images covers
        for datacls in [x for x in datacls_list if x.to_assign]:
            if datacls.is_template_cover:
                for image in template.media:
                    image_gid = image.gid

                    if (image_gid == datacls.code) and (image_gid != template.featured_media_gid):
                        template.set_image_as_cover(image_gid)

            if not datacls.variant_code:
                continue

            variants_append_media.append({
                'mediaIds': [self.gql.MediaImage.create_gid(datacls.code_int)],
                'variantId': self.gql.ProductVariant.create_gid(datacls.variant_code),
            })

        if variants_append_media:
            template.append_images_to_variants(variants_append_media)

        return datacls_list

    @not_implemented
    def export_attribute(self, attribute):
        """
        There is no Shopify REST API endpoint for `Attributes`.
        Moreover, the is no way to reuse attribute ID because for the each products the same
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

    @check_scope('write_products')
    def export_category(self, category):
        _logger.info('Shopify "%s": export_category()', self._integration_name)

        collection = self.gql.Collection.create(category['name'])

        return collection.id_str

    @check_scope('write_products', 'write_inventory')
    def export_inventory(self, inventory: list):
        _logger.info('Shopify "%s": export_inventory()', self._integration_name)

        result, items_activate_tracked = [], []
        inventory_items = list(inventory.items())

        for i in range(0, len(inventory_items), 250):
            payload_data = list()
            prices_data = defaultdict(list)
            batch = inventory_items[i:i + 250]

            for complex_id, item_data_list in batch:
                __, variant_id = self._parse_product_external_code(complex_id)
                prices_data[variant_id] = item_data_list

            if prices_data:
                ProductVariant = self.gql.ProductVariant

                variants = ProductVariant.get_by_ids_for_inventory_items(list(prices_data.keys()))

                for variant in variants:
                    item = variant.inventory_item
                    data_list = prices_data[variant.id_str]

                    item_result = []
                    for item_data in data_list:
                        location_id = item_data['external_location_id']
                        args = (item.id, location_id, item_data['qty'])

                        if variant.has_activated_location(location_id):
                            if not item.tracked:
                                items_activate_tracked.append(item)
                        else:
                            # Activate item
                            self.gql.InventoryItem.activate_inventory_item(*args)

                        payload_data.append(args)

                        item_result.append({
                            'inventory_item_id': item.id_str,
                            'location_id': args[1],
                            'available': args[2],
                        })

                    result.append((variant.external_id, item_result, ''))

            # 1. Update quantities
            if payload_data:
                self.gql.InventoryItem.update_quantity_batch(payload_data)

        # 2. Update items
        for item in items_activate_tracked:
            item.update_item(tracked=True)

        return result

    @check_scope(
        'write_fulfillments',
        'write_merchant_managed_fulfillment_orders',
    )
    def export_tracking(self, sale_order_id: str, tracking_data_list: List[Dict], force_done=False) -> list:
        tracking_data_list_ = sorted(
            tracking_data_list,
            key=lambda x: int(x['external_location_id'] or 0),
            reverse=True,
        )

        result_list, end = [], len(tracking_data_list_)

        for idx, picking_data in enumerate(tracking_data_list_, start=1):
            result = self.send_picking(sale_order_id, picking_data, force_done=(force_done and idx == end))
            result_list.extend(result)

        return [x for x in result_list if x]

    @check_scope(
        'write_fulfillments',
        'write_merchant_managed_fulfillment_orders',
    )
    def send_picking(self, sale_order_id: str, picking_data: dict, force_done : bool = False) -> list:
        location_id = int(picking_data.get('external_location_id') or 0)
        lines = [{'id': int(x['id']), 'qty': int(x['qty'])} for x in picking_data['lines']]

        picking_data.update(
            lines=lines,
            external_location_id=location_id,
        )

        # Make a copy of original picking data
        picking_data_orig = deepcopy(picking_data)

        order = self.gql.Order.set(id=sale_order_id)
        fulfill_orders = order.get_fulfillment_orders(open_or_in_progress=True)

        if location_id:
            # Check if there are any moves between fulfill orders must be done before fulfilling
            is_anything_was_moved = self._prepare_fulfillment_orders(fulfill_orders, picking_data)

            if is_anything_was_moved:
                # Refresh the fulfill orders and fulfill them (using original picking data)
                fulfill_orders = order.get_fulfillment_orders(open_or_in_progress=True)

            fulfill_orders.sort(key=lambda x: x.location.id == location_id, reverse=True)

        fulfillments = []

        # Start for fulfilling orders (lines from picking data must fit existing fulfill orders)
        for fulfill_order in fulfill_orders:
            lines_data = []

            if force_done:
                lines_data = fulfill_order._prepare_fulfillment_lines_data(),
            else:
                for line in picking_data['lines']:
                    data = fulfill_order._prepare_fulfillment_single_line_data(line['id'], line['qty'])

                    if data:
                        lines_data.append(data)
                        line['qty'] -= data['quantity']

            if lines_data:
                fulfillment = fulfill_order.fulfill(
                    carrier=picking_data_orig['carrier_code'] or '',
                    tracking_numbers=picking_data_orig['tracking'] and [picking_data_orig['tracking']] or '',
                    url=picking_data_orig['carrier_tracking_url'] or None,
                    lines_data=lines_data,
                    notify_customer=True,
                )
                fulfillments.append(fulfillment)

            if not force_done:
                if not any(x['qty'] for x in picking_data['lines']):
                    break

        return [x.to_odoo_format() for x in fulfillments]

    def _prepare_fulfillment_orders(self, fulfill_orders, picking_data):
        # If there is location ID, we need to find out which items must be moved before fulfilling
        picking_data_copy = deepcopy(picking_data)
        location_id = picking_data_copy['external_location_id']

        fulfill_orders_with_same_location = [x for x in fulfill_orders if x.location.id == location_id]
        fulfill_orders_with_different_location = [x for x in fulfill_orders if x.location.id != location_id]

        # Step 1. Check orders with the same location
        for fulfill_order in fulfill_orders_with_same_location:
            for line in picking_data_copy['lines']:
                data = fulfill_order._prepare_fulfillment_single_line_data(line['id'], line['qty'])

                if data:
                    line['qty'] -= data['quantity']

        # Step 2. Filter lines with zero quantity in picking data
        picking_data_copy['lines'] = [x for x in picking_data_copy['lines'] if x['qty']]

        # Exit if nothing to fulfill
        is_anything_was_moved = False

        if not picking_data_copy['lines']:
            return is_anything_was_moved

        # Step 3. Check orders with different location
        line_ids_to_fullfill = [x['id'] for x in picking_data_copy['lines']]

        def _sort_fulfillment_orders(o):
            # Sort by number of matching line items
            line_item_ids = [x.sale_line_item.id_str for x in o.line_items if x.remaining_quantity]
            return len(set(line_item_ids) & set(line_ids_to_fullfill))

        # Leave only fulfill_orders that have different location
        fulfill_orders_with_different_location.sort(key=_sort_fulfillment_orders, reverse=True)

        for fulfill_order in fulfill_orders_with_different_location:
            lines_to_move = []

            for line in picking_data_copy['lines']:
                data = fulfill_order._prepare_fulfillment_single_line_data(line['id'], line['qty'])

                if data:
                    line['qty'] -= data['quantity']

                    # Save data for moving
                    lines_to_move.append(data)

            if lines_to_move:
                if lists_are_equal(lines_to_move, fulfill_order._prepare_fulfillment_lines_data()):
                    fulfill_order.move(location_id)
                else:
                    new_fulfill_order = fulfill_order.split(lines_to_move)
                    new_fulfill_order.move(location_id)

                is_anything_was_moved = True

            # If there is no more lines to fulfill, break the loop
            if not any(x['qty'] for x in picking_data_copy['lines']):
                break

        return is_anything_was_moved

    @check_scope('write_orders')
    def send_sale_order_status(self, external_order_id: str, vals: dict):
        method_name = f'_send_sub_status_{vals["status"]}'

        if hasattr(self, method_name):
            return getattr(self, method_name)(external_order_id, vals)

        raise NotImplementedError(
            _(
                'The Shopify export method "%s" is not yet implemented. Please contact VentorTech '
                'support at support@ventor.tech to report this issue. When contacting support, '
                'provide the following:\n'
                '1. The exact status value: "%s".\n'
                '2. The Shopify instance URL (e.g., "xxx.myshopify.com").\n\n'
                'For secure sharing of sensitive information, use https://share.ventor.tech.'
            ) % (method_name, vals["status"])
        )

    def _send_sub_status_paid(self, external_order_id: str, *args, **kw):  # TODO
        order = self.gql.Order.set(id=external_order_id)
        order.mark_as_paid()

        use_customer_currency = self._settings['use_customer_currency']

        return [x.to_odoo_format(use_customer_currency) for x in order.transactions]

    @add_dynamic_kwargs
    def order_fetch_kwargs(self, **kw):
        params_str = self._default_order_domain()

        integration = self._get_integration(kw)

        receive_from = integration.last_receive_orders_datetime_str
        if receive_from:
            params_str += f' AND updated_at:>=\\"{receive_from}\\"'

        cut_off_datetime = integration.orders_cut_off_datetime_str
        if cut_off_datetime:
            params_str += f' AND created_at:>=\\"{cut_off_datetime}\\"'

        return params_str

    @add_dynamic_kwargs
    @check_scope('read_orders')
    def receive_orders(self, **kw):
        _logger.info('Shopify "%s": receive_orders()', self._integration_name)

        params_str = self.order_fetch_kwargs()(**kw)

        orders = self.gql.Order.get_batch_body_minimal(filter_params=params_str)

        return [x.to_odoo_format() for x in orders]

    @check_scope('read_orders')
    def receive_order(self, order_id):
        """
        Receive and process a single order from Shopify.
        """
        order = self.gql.Order.get_by_pk(order_id, raise_if_not_found=False)

        if not order:
            return {}

        return order.to_odoo_format()

    @add_dynamic_kwargs
    @check_scope(
        'read_orders',
        'read_merchant_managed_fulfillment_orders',
    )
    def parse_order(self, input_file: dict, **kw) -> dict:
        _logger.info('Shopify "%s": parse_order() from input file.', self._integration_name)

        order = self.gql.Order.set(**input_file)

        result = order.parse(
            use_customer_currency=self._settings['use_customer_currency'],
        )

        return result

    def get_delivery_methods(self):
        _logger.info('Shopify "%s": get_delivery_methods()', self._integration_name)

        result = set()
        fetched_qty = control_qty = 0
        max_limit = self.batch_size

        # 1. Get delivery methods from fulfillment orders (DeliveryMethodType == shipping)
        FulfillmentOrder = self.gql.FulfillmentOrder

        while True:
            orders = FulfillmentOrder.get_batch_for_delivery_methods()

            fetched_qty += len(orders)

            for record in orders:
                delivery = record.delivery_method
                if not delivery:
                    continue

                if not delivery.method_type.is_shipping or not delivery.is_valid:
                    continue

                result.add(
                    delivery.to_odoo_format(to_tuple=True)
                )

            if (len(orders) < FulfillmentOrder._request_limit) or not FulfillmentOrder.cursor:
                break

            if fetched_qty >= max_limit * 10:
                _logger.warning('%s: get_delivery_methods() reached max limit of 10 times.', self._integration_name)
                break

            if fetched_qty >= max_limit:
                if control_qty == len(result):
                    break

            control_qty = len(result)

        # 2. Get the standard delivery methods (DeliveryMethodType in [local, pick_up, pickup_point, retail])
        standard_method_types = self.gql.DeliveryMethodType.to_list(exclude=['none', 'shipping'])
        for method_type in standard_method_types:
            delivery = self.gql.DeliveryMethod._to_odoo_format_from_type(method_type['value'], to_tuple=True)
            result.add(delivery)

        return [dict(x) for x in result]

    def get_single_tax(self, tax_id: str) -> dict:
        _logger.info('Shopify "%s": get_single_tax()', self._integration_name)
        # :tax_id: formatted string like 'Sales Tax (LX799/XL) 20.3% [excluded]'
        return self.gql.TaxLine.parse_formatted_tax(tax_id)

    @check_scope('read_orders')
    def get_taxes(self, **kw):
        _logger.info('Shopify "%s": get_taxes()', self._integration_name)

        result = set()
        fetched_qty = control_qty = 0
        max_limit = self.batch_size

        Order = self.gql.Order

        while True:
            orders = Order.get_batch_for_taxes()

            fetched_qty += len(orders)

            for record in orders:
                taxes = record.tax_lines \
                    + sum([x.tax_lines for x in record.line_items], []) \
                    + sum([x.tax_lines for x in record.shipping_lines], [])

                for tax in taxes:
                    result.add(
                        tax.to_odoo_format(taxes_included=record.is_taxable)
                    )

            if (len(orders) < Order._request_limit) or not Order.cursor:
                break

            if fetched_qty >= max_limit * 10:
                _logger.warning('%s: get_taxes() reached max limit of 10 times.', self._integration_name)
                break

            if fetched_qty >= max_limit:
                if control_qty == len(result):
                    break

            control_qty = len(result)

        return [self.gql.TaxLine.parse_formatted_tax(x) for x in result]

    @check_scope('read_orders')
    def get_payment_methods(self, **kw):
        _logger.info('Shopify "%s": get_payment_methods()', self._integration_name)

        result = set()
        fetched_qty = control_qty = 0
        max_limit = self.batch_size

        Order = self.gql.Order
        OrderTransaction = self.gql.OrderTransaction.cls

        while True:
            orders = Order.get_batch_for_payment_methods()

            fetched_qty += len(orders)

            for record in orders:
                for name in record.payment_gateway_names:
                    code = OrderTransaction.format_payment_code(name)

                    if not name:
                        name = OrderTransaction.PAYMENT_NOT_DEFINED

                    result.add(
                        (('id', code), ('name', name))
                    )

            if (len(orders) < Order._request_limit) or not Order.cursor:
                break

            if fetched_qty >= max_limit * 10:
                _logger.warning('%s: get_payment_methods() reached max limit of 10 times.', self._integration_name)
                break

            if fetched_qty >= max_limit:
                if control_qty == len(result):
                    break

            control_qty = len(result)

        # Add default payment method
        result.add(
            (
                ('id', OrderTransaction.format_payment_code(False)),
                ('name', OrderTransaction.PAYMENT_NOT_DEFINED),
            )
        )

        return [dict(x) for x in result]

    @check_scope('read_locales')
    def get_languages(self):
        _logger.info('Shopify "%s": get_languages()', self._integration_name)
        return [x.to_odoo_format() for x in self.shop.locales if x.published]

    @check_scope('read_products')
    def get_attributes(self) -> list:
        _logger.info('Shopify "%s": get_attributes()', self._integration_name)
        return self._get_products_options('get_attributes')

    def get_attribute_values(self) -> list:
        _logger.info('Shopify "%s": get_attribute_values()', self._integration_name)
        return self._get_products_options('get_attribute_values')

    def _get_products_options(self, option_name: str) -> list:
        _logger.info('Shopify "%s": get_attribute_values()', self._integration_name)

        Product = self.gql.Product
        body = Product.PRODUCT_GET_ATTRIBUTES_BODY

        products = Product.get_batch(
            body=body,
            arguments='sortKey: ID, reverse: true',
            filter_params=self._default_product_domain(),
            limit=math.inf,
        )

        result, tmp = [], set()

        for product in products:
            for attribute_value in getattr(product, option_name)():
                if attribute_value['id'] not in tmp:
                    result.append(attribute_value)

                tmp.add(attribute_value['id'])

        return result

    def get_product_tags(self):
        _logger.info('Shopify "%s": get_product_tags()', self._integration_name)
        return self.shop.product_tags  # TODO: what if tags more than 250?

    @check_scope('read_publications')
    def get_sale_channels(self):
        _logger.info('Shopify: get_sale_channels()')
        publications = self.gql.Publication.get_batch()
        return [x.to_odoo_format() for x in publications if x.catalog]

    def get_pricelists(self):
        _logger.info('Shopify "%s": get_pricelists(). Not implemented.', self._integration_name)
        return []

    @check_scope('read_locations')
    def get_locations(self):
        _logger.info('Shopify "%s": get_locations().', self._integration_name)
        locations = self.gql.Location.get_batch()
        return [x.to_odoo_format() for x in locations if x.active]

    @check_scope('read_shipping')
    def get_countries(self):
        _logger.info('Shopify "%s": get_countries()', self._integration_name)
        countries = self._get_delivery_countries()
        return [x.to_odoo_format() for x in countries]

    @check_scope('read_shipping')
    def get_states(self):
        _logger.info('Shopify "%s": get_states()', self._integration_name)

        countries = self._get_delivery_countries()

        result = []
        for country in countries:
            result.extend(country.provinces_to_odoo_format())

        return result

    def _get_delivery_countries(self):
        delivery_profiles = self.gql.DeliveryProfile.get_batch()

        result = []
        for profile in delivery_profiles:
            result.extend(profile.get_countries())

        return list(set(flatten_recursive(result)))

    @check_scope('read_products')
    def get_categories(self):
        _logger.info('Shopify "%s": get_categories()', self._integration_name)

        collections = self.gql.Collection.get_batch(
            filter_params='collection_type:custom',
        )
        return [x.to_odoo_format() for x in collections]

    @check_scope('read_products', 'read_markets')
    def get_catalogs(self):
        _logger.info('Shopify "%s": get_catalogs()', self._integration_name)

        market_catalogs = self.gql.MarketCatalog.fetch_all()
        company_location_catalogs = self.gql.CompanyLocationCatalog.fetch_all()

        catalogs = market_catalogs + company_location_catalogs

        return [x.to_odoo_format() for x in catalogs]

    def get_sale_order_statuses(self):
        _logger.info('Shopify "%s": get_sale_order_statuses()', self._integration_name)

        status_list = self.gql.OrderDisplayFulfillmentStatus.to_list(
            exclude=[
                'open',
                'pending_fulfillment',
                'restocked',
                'shipped',
                'unshipped',
                'partial',
            ],
        ) + self.gql.OrderDisplayFinancialStatus.to_list()

        result, tmp = [], []
        for data in status_list:
            name = data['name']
            if name in tmp:
                continue

            result.append({
                'id': name,
                'name': data['string'],
                'external_reference': False,
            })
            tmp.append(name)

        return result

    def get_product_template_ids(self):
        _logger.info('Shopify "%s": get_product_template_ids()', self._integration_name)

        templates = self.gql.Product.get_batch(
            body='id',
            arguments='sortKey: CREATED_AT',
            filter_params=self._default_product_domain(),
            limit=math.inf,
        )

        return [x.id_str for x in templates]

    @add_dynamic_kwargs
    @check_scope('read_products')
    def get_product_templates(self, template_ids, **kw):
        _logger.info('Shopify "%s": get_product_templates()', self._integration_name)

        if not template_ids:
            return dict(), list(), list()

        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name
        variant_barcode = integration.variant_barcode_api_name

        def parse_variant(template, variant):
            return {
                'id': variant.external_id,
                'name': template.title,
                'external_reference': variant[variant_reference],
                'barcode': variant[variant_barcode],
                'ext_product_template_id': template.id_str,
                'attribute_value_ids': variant.get_attribute_values(),
            }

        result = []
        templates = self.gql.Product.get_by_ids(template_ids)  # !!! len(template_ids) <= 250

        for template in templates:
            external_ref = barcode = None
            variants = template.variants

            if len(variants) == 1:
                barcode = getattr(variants[0], variant_barcode) or None
                external_ref = getattr(variants[0], variant_reference) or None

            result.append({
                'id': template.id_str,
                'name': template.title,
                'barcode': barcode,
                'external_reference': external_ref,
                'variants': [parse_variant(template, x) for x in variants],
            })

        # TODO: Implement errors handling
        errors = list()
        failed_external_template_ids = list()

        return {x['id']: x for x in result}, failed_external_template_ids, errors

    @check_scope('read_customers')
    def get_customer_ids(self, datetime_since: 'datetime' = None):
        _logger.info('Shopify "%s": get_customer_ids()', self._integration_name)

        customers = self.gql.Customer.get_batch(
            body='id updatedAt',
            arguments='sortKey: UPDATED_AT',
            limit=math.inf,
        )

        if datetime_since:
            customers = (
                x for x in customers
                if (parser.isoparse(x.updated_at).replace(tzinfo=None) > datetime_since)
            )
        return [x.id_str for x in customers]

    @check_scope('read_customers')
    def get_customer_and_addresses(self, customer_id):
        _logger.info('Shopify "%s": get_customer_and_addresses()', self._integration_name)

        customer = self.gql.Customer.get_by_pk(customer_id, raise_if_not_found=False)

        if not customer:
            return {}, []

        customer_data, address_list = customer.parse()

        for address in address_list:
            if address.get('default'):
                address['type'] = 'invoice'

        return customer_data, address_list

    @check_scope('read_products', 'read_inventory')
    def get_product_for_import(self, external_template_id: str):
        _logger.info('Shopify "%s": get_product_for_import()', self._integration_name)

        product = self.gql.Product.get_by_pk(external_template_id, raise_if_not_found=False)
        if not product:
            raise UserError(_(
                'Product with id "%s" does not exist in Shopify. Please verify the product ID '
                'and ensure it is available in your Shopify store.'
                ) % external_template_id
            )

        # Parse template images
        external_images = []
        for media in product.media:
            is_cover = (media.gid == product.featured_media_gid)

            if is_cover or not product.image_exists_on_variants(media.gid):
                external_images.append(
                    ExternalImage(
                        code=media.gid,
                        name=media.name,
                        ttype=ProductType.PRODUCT_TEMPLATE,
                        template_code=external_template_id,
                        src=media.src,
                        is_cover=is_cover,
                        integration_id=self._integration_id,
                    ),
                )

        # Parse variants
        variant_image_ids = []
        variants = product.variants

        for variant in variants:
            # Parse variant images
            for media in variant.media:
                external_images.append(
                    ExternalImage(
                        code=media.gid,
                        name=media.name,
                        ttype=ProductType.PRODUCT_PRODUCT,
                        template_code=external_template_id,
                        variant_code=str(variant.id),
                        src=media.src,
                        is_cover=True,  # The Shopify variant has only one image (relates to the template image)
                        integration_id=self._integration_id,
                    )
                )
                variant_image_ids.append(media.gid)

        # Prepare template dict
        product_dict = product.to_dict(simple_identifier=True)
        product_dict['_attributes'] = [x['id'] for x in product.get_attribute_values()]

        # Prepare variants list
        variant_list = []
        for variant in variants:
            variant_dict = variant.to_dict(simple_identifier=True)
            variant_dict['_attribute_value_ids'] = variant.get_attribute_values()
            variant_list.append(variant_dict)

        product_dict['_variants_count'] = len(variant_list)
        return product_dict, variant_list, [], external_images

    def get_image_data(self, src):
        response = requests.get(src)

        if response.ok:
            return base64.b64encode(response.content)

        raise ShopifyApiError(response.text)

    @not_implemented
    def get_products_for_accessories(self):
        return [], {}

    @check_scope('read_inventory')
    def get_stock_levels(self, external_location_id: str) -> dict:
        _logger.info('Shopify "%s": get_stock_levels(%s)', self._integration_name, external_location_id)

        location = self.gql.Location.set(id=external_location_id)
        inventory_levels = location.get_inventory_levels()

        result = dict()
        for record in inventory_levels:  # TODO: not checked existing product mappings
            result[record.variant.external_id] = record.get_quantity()

        return result

    @add_dynamic_kwargs
    @check_scope('read_products')
    def get_templates_and_products_for_validation_test(self, **kw):
        """Shopify product has no reference (sku) and barcode, only its variant."""
        _logger.info('Shopify "%s": get_templates_and_products_for_validation_test()', self._integration_name)

        integration = self._get_integration(kw)
        variant_reference = integration.variant_reference_api_name
        variant_barcode = integration.variant_barcode_api_name

        # TODO: what if product-variants more than 250?
        body = 'id title variants(first: 250) { nodes { id title %s %s product { id } } }' % (
            variant_reference,
            variant_barcode,
        )

        templates = self.gql.Product.get_batch(
            body=body,
            arguments='sortKey: CREATED_AT',
            filter_params=self._default_product_domain(),
            limit=math.inf,
        )

        data = dict()
        for template in templates:
            parsed_data = template._serialize_for_validation_test(
                sku=variant_reference,
                barcode=variant_barcode,
            )
            data[template.id_str] = parsed_data

        return TemplateHub(list(itertools.chain.from_iterable(data.values())))

    @check_scope('write_orders')
    def cancel_order(self, external_id: str, params: dict):
        order = self.gql.Order.set(id=external_id)
        args = (
            params['notify_cutomer'],
            params['refund'],
            params['restock'],
            params['reason'],
            params['staff_note'],
        )
        return order.cancel(*args)

    @check_scope('write_merchant_managed_fulfillment_orders')
    def cancel_fulfillment(self, external_id: str):
        fulfillment = self.gql.Fulfillment.set(id=external_id)
        return fulfillment.cancel()

    def _get_url_pattern(self, wrap_li=True):
        pattern = f'<a href="{self.admin_url}/products/%s/variants/%s" target="_blank">%s</a>'
        return f'<li>{pattern}</li>' if wrap_li else pattern

    def _prepare_url_args(self, record):
        if record.parent_id:
            return (record.parent_id, record.id, record.format_name)
        return (record.id, record.id, record.format_name)

    def _convert_to_html(self, id_list):
        pattern = self._get_url_pattern()
        arg_list = [self._prepare_url_args(x) for x in id_list]

        return ''.join([pattern % args for args in arg_list])

    def _default_product_domain(self):
        return self.get_settings_value('import_products_filter') or dict()

    def _default_order_domain(self):
        args = []

        def prepare_elements(name, element_str: str) -> str:
            elements = list(map(lambda x: x.strip(), element_str.split(',')))

            if len(elements) > 1:
                value = ' OR '.join(f'({name}:{x})' for x in elements)
                return f'({value})'

            return f'{name}:{elements[0]}'

        # 1. Common status
        status = self.get_settings_value('receive_order_statuses')
        if status:
            args.append(
                prepare_elements('status', status)
            )

        # 2. Financial status
        financial_status = self.get_settings_value('receive_order_financial_statuses')
        if financial_status:
            args.append(
                prepare_elements('financial_status', financial_status)
            )

        # 3. Fulfillment status
        fulfillment_status = self.get_settings_value('receive_order_fulfillment_statuses')
        if fulfillment_status:
            status_list = fulfillment_status.split(',')

            fulfilled = OrderDisplayFulfillmentStatus.fulfilled.name
            if fulfilled in status_list:
                status_list.remove(fulfilled)
                status_list.append(OrderDisplayFulfillmentStatus.shipped.name)
                fulfillment_status = ','.join(status_list)

            args.append(
                prepare_elements('fulfillment_status', fulfillment_status)
            )

        return ' AND '.join(args)

    def order_limit_value(self):
        return self.gql.Order._request_limit

    @check_scope('read_metaobjects')
    def get_customer_metafields_by_id(self, customer_id: str) -> list:
        metafield_data = self.gql.Customer.set(id=customer_id).get_metafields()
        return [x.to_dict() for x in metafield_data]

    @check_scope('read_metaobjects')
    def get_order_metafields_by_id(self, order_id: str) -> list:
        metafield_data = self.gql.Order.set(id=order_id).get_metafields()
        return [x.to_dict() for x in metafield_data]

    @check_scope('read_metaobject_definitions')
    def get_metafields(self, entity_name: str) -> list:
        metafields = self.gql.MetafieldDefinition.get_batch(
            arguments=f'ownerType: {entity_name.upper()}',
        )
        return [x.to_odoo_format() for x in metafields]

    def get_order_url(self, external_order_id: str) -> str:
        return f'{self.admin_url}/orders/{external_order_id}'

    def get_product_url(self, external_product_code: str) -> str:
        return f'{self.admin_url}/products/{external_product_code}'

    def _prepare_converted_fields(self, fields_dict):
        result = dict()

        for field_name, field_value in fields_dict.items():

            # 1. Handle meta fields (include translations)
            if field_name == 'metafields':
                meta_data_list = []

                for data in field_value:
                    data_copy = deepcopy(data)

                    data_copy['value'] = self.parse_translated_value(data['value'], lang=self.lang)
                    meta_data_list.append(data_copy)

                if not meta_data_list:
                    continue

                value = meta_data_list

            # 2. Handle translatable fields
            elif self.is_translated_value(field_value):
                value = self.parse_translated_value(field_value, lang=self.lang)

            # 3. Handle simple fields
            else:
                value = field_value

            result[field_name] = value

        return result
