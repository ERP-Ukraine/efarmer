#  See LICENSE file for full copyright and licensing details.

import re
import logging
from typing import List

from odoo import api, models, fields, _

from .fields.send_fields import SendFieldsShopify
from .fields.send_fields_product_product import SendFieldsProductProductShopify
from .fields.send_fields_product_template import SendFieldsProductTemplateShopify
from .fields.receive_fields import ReceiveFieldsShopify
from .fields.receive_fields_product_product import ReceiveFieldsProductProductShopify
from .fields.receive_fields_product_template import ReceiveFieldsProductTemplateShopify
from ..shopify.tools import parse_graphql_id
from .external.external_sale_channel import NO_CHANNEL_EXTERNAL_ID

from ..shopify_api import ShopifyAPIClient, SHOPIFY

_logger = logging.getLogger(__name__)


class SaleIntegration(models.Model):
    _inherit = 'sale.integration'

    type_api = fields.Selection(
        selection_add=[(SHOPIFY, 'Shopify')],
        ondelete={
            SHOPIFY: 'cascade',
        },
    )

    use_customer_currency = fields.Boolean(
        string='Import Orders in Customer Currency',
        copy=False,
        help=(
            'Check this option to ensure that imported orders is recorded using the customer\'s '
            'currency, preserving the original currency used during the sale.'
        ),
    )

    order_metafield_mapping_ids = fields.One2many(
        comodel_name='integration.metafield.mapping',
        inverse_name='integration_id',
        string='Order Metafield Mappings',
        domain=[('type', '=', 'order')],
        help=(
            'Defines the mappings between the order metafields in the external system and the '
            'fields in Odoo.'
        ),
    )

    customer_metafield_mapping_ids = fields.One2many(
        comodel_name='integration.metafield.mapping',
        inverse_name='integration_id',
        string='Customer Metafield Mappings',
        domain=[('type', '=', 'customer')],
        help=(
            ' Defines the mappings between the customer metafields in the external system and the '
            'fields in Odoo.'
        ),
    )

    invalid_location_mapping = fields.Boolean(
        string='Invalid Location Mapping',
        compute='_compute_invalid_location_mapping',
    )

    integration_channel_ids = fields.Many2many(
        comodel_name='external.sale.channel',
        string='Sale Channels',
        domain='[("integration_id", "=", id)]',
        help=(
            'Select the sales channels you want to import orders from in this e-commerce store. '
            'Leave this field empty if you want to import orders from all sales channels. '
            'A special "No Channel" option is available to include orders that are not associated '
            'with any specific sales channel. This can be useful for capturing orders that may have '
            'been created outside of the normal channel structure.'
        ),
    )

    def is_shopify(self):
        self.ensure_one()
        return self.type_api == SHOPIFY

    @api.depends('location_line_ids')
    def _compute_invalid_location_mapping(self):
        for rec in self:
            if rec.is_shopify():
                value = len(rec.location_line_ids.mapped('warehouse_id')) < len(rec.location_line_ids)
            else:
                value = False

            rec.invalid_location_mapping = value

    def is_integration_cancel_allowed(self):
        if len(self) == 1 and self.is_shopify():
            return True
        return super().is_integration_cancel_allowed()

    def _get_cancel_order_view_id(self):
        if self.is_shopify():
            return self.env.ref('integration_shopify.sale_order_cancel_integration_shopify_view_form').id
        return super()._get_cancel_order_view_id()

    def _set_default_template_reference_id(self):
        if self.is_shopify():
            self.template_reference_id = self.env.ref(
                'integration_shopify.shopify_template_reference_private').id
            return bool(self.template_reference_id)
        return super()._set_default_template_reference_id()

    def _set_default_product_reference_id(self):
        if self.is_shopify():
            self.product_reference_id = self.env.ref(
                'integration_shopify.shopify_ecommerce_field_variant_default_code').id
            return bool(self.product_reference_id)
        return super()._set_default_product_reference_id()

    def _set_default_template_barcode_id(self):
        if self.is_shopify():
            self.template_barcode_id = self.env.ref(
                'integration_shopify.shopify_template_barcode_private').id
            return bool(self.template_barcode_id)
        return super()._set_default_template_barcode_id()

    def _set_default_product_barcode_id(self):
        if self.is_shopify():
            self.product_barcode_id = self.env.ref(
                'integration_shopify.shopify_ecommerce_field_variant_barcode').id
            return bool(self.product_barcode_id)
        return super()._set_default_product_barcode_id()

    def get_class(self):
        self.ensure_one()
        if self.is_shopify():
            return ShopifyAPIClient
        return super(SaleIntegration, self).get_class()

    def action_active(self):
        result = super(SaleIntegration, self).action_active()

        if self.is_shopify():
            adapter = self._build_adapter()
            weight_uom = adapter._client._get_weight_uom()
            self.set_settings_value('weight_uom', weight_uom)

        return result

    def export_sale_order_status(self, order):
        res = super(SaleIntegration, self).export_sale_order_status(order)
        if not self.is_shopify():
            return res

        if res:
            vals = order._prepare_vals_for_sale_order_status()
            if vals['status'] == 'paid':
                order._apply_values_from_external({'order_transactions': [res]})

        return res

    def export_tracking(self, pickings):
        """Redefined method in order to apply external fulfillments"""
        res = super(SaleIntegration, self).export_tracking(pickings)
        if not self.is_shopify():
            return res

        if res:
            order = pickings.mapped('sale_id')
            order._apply_values_from_external({'order_fulfillments': res})
            order.external_fulfillment_ids.mark_done()

        return res

    def _ensure_settings(self):
        if self.is_shopify():
            self._ensure_not_null_setting(['url', 'version', 'key'])

        return super()._ensure_settings()

    def advanced_inventory(self):
        if self.is_shopify():
            return True
        return super(SaleIntegration, self).advanced_inventory()

    def _handle_mapping_data(self, template, t_mapping, v_mapping_list, ext_records_to_update):
        result = super(SaleIntegration, self)\
            ._handle_mapping_data(template, t_mapping, v_mapping_list, ext_records_to_update)

        if self.is_shopify():
            # Create attribute/values mappings
            external_data = t_mapping['attribite_values']['external_data']
            existing_ids = t_mapping['attribite_values']['existing_ids']
            attributes_data, attribite_values_data = list(), list()

            for data in external_data:
                if data['id'] in existing_ids:
                    continue
                attributes_data.append(
                    {'id': data['id_group'], 'name': data['id_group_name']},
                )
                attribite_values_data.append(data)

            if attributes_data:
                external_attribute_ids, __ = self._import_external(
                    'integration.product.attribute.external',
                    '',
                    external_data=attributes_data,
                )
                external_attribute_ids._map_external(attributes_data)

            if attribite_values_data:
                external_attribute_value_ids, __ = self._import_external(
                    'integration.product.attribute.value.external',
                    '',
                    external_data=attribite_values_data,
                )
                external_attribute_value_ids._map_external(attribite_values_data)

        return result

    def _fetch_external_tax(self, tax_id):
        if self.is_shopify():
            # tax_id: 'Sales Tax (LX799/XL) 20.3% [excluded]'
            tax_rate = re.findall(r'-?\d+\.?\d*', tax_id)[-1]  # parse `20.3`
            tax_option = re.findall(r'\[(\w+)\]', tax_id)[-1]  # parse `excluded`

            vals = {
                'id': tax_id,
                'name': tax_id,
                'rate': tax_rate,
                'price_include': {'excluded': False, 'included': True}[tax_option],
            }
            return vals

        return super(SaleIntegration, self)._fetch_external_tax(tax_id)

    def _retrieve_webhook_routes(self):
        if self.is_shopify():
            return {
                'orders': [
                    ('Order Create', 'orders/create'),
                    ('Order Paid', 'orders/paid'),
                    ('Order Cancel', 'orders/cancelled'),
                    ('Order Fullfill', 'orders/fulfilled'),
                    ('Order Partially Fullfill', 'orders/partially_fulfilled'),
                ],
                'products': [
                    ('Product Create', 'products/create'),
                    ('Products Update', 'products/update'),
                    ('Products Delete', 'products/delete'),
                ],
            }

        return super(SaleIntegration, self)._retrieve_webhook_routes()

    def force_set_inactive(self):
        if self.is_shopify():
            return {'status': 'draft'}
        return super(SaleIntegration, self).force_set_inactive()

    def _get_error_webhook_message(self, error):
        if not self.is_shopify():
            return super(SaleIntegration, self)._get_error_webhook_message(error)

        return _('Shopify Webhook Error: %s') % error.args[0]

    def init_send_field_converter(self, odoo_obj=False):
        if not self.is_shopify():
            return super(SaleIntegration, self).init_send_field_converter(odoo_obj)

        if getattr(odoo_obj, '_name', '') == 'product.template':
            return SendFieldsProductTemplateShopify(self, odoo_obj)
        if getattr(odoo_obj, '_name', '') == 'product.product':
            return SendFieldsProductProductShopify(self, odoo_obj)
        return SendFieldsShopify(self, odoo_obj)

    def init_receive_field_converter(self, odoo_obj=False, external_obj=False):
        if not self.is_shopify():
            return super(SaleIntegration, self).init_receive_field_converter(odoo_obj, external_obj)

        if getattr(odoo_obj, '_name', '') == 'product.template':
            return ReceiveFieldsProductTemplateShopify(self, odoo_obj, external_obj)
        if getattr(odoo_obj, '_name', '') == 'product.product':
            return ReceiveFieldsProductProductShopify(self, odoo_obj, external_obj)
        return ReceiveFieldsShopify(self, odoo_obj, external_obj)

    def _get_weight_integration_fields(self):
        if not self.is_shopify():
            return super(SaleIntegration, self)._get_weight_integration_fields()

        return [
            'integration_shopify.shopify_ecommerce_field_variant_weight',
        ]

    def update_metafields(self):
        """
        Update metafields associated with customers from the external system (e.g., Shopify).
        """
        if not self.is_shopify():
            return False

        external_entity = self.env.context.get('external_entity')
        assert external_entity, _('Missed context variable "external_entity"')

        store_metafields = self.adapter.get_metafields(external_entity)

        if not store_metafields:
            return self._raise_notification(
                'warning',
                f'There are no {external_entity.title()} metafields in your Shopify store',
            )

        Metafield = self.env['external.metafield']
        actual_metafields = self.env['external.metafield'].browse()

        for metafield in store_metafields:
            # Search for an existing metafield with the same name and key
            record = Metafield.search([
                ('integration_id', '=', self.id),
                ('type', '=', external_entity),
                ('metafield_name', '=', metafield['name']),
                ('metafield_key', '=', metafield['key']),
            ])

            if not record:
                record = Metafield.create({
                    'integration_id': self.id,
                    'type': external_entity,
                    'metafield_name': metafield['name'],
                    'metafield_key': metafield['key'],
                    'metafield_type': metafield.get('type', {}).get('name', ''),
                })

            actual_metafields |= record

        # Delete meta fields that don't exist in Shopify
        metafields = Metafield.search([
            ('integration_id', '=', self.id),
            ('type', '=', external_entity),
        ])
        (metafields - actual_metafields).unlink()

        return self._raise_notification(
            'success',
            f'{external_entity.title()}s metafields were successfully updated',
        )

    def get_object_metafields(self, entity_name: str, entity_id: str) -> List:
        """
        Get metafields associated with a specific entity.
        :parameters:
            - entity_name: customer / order
        """
        if self.is_shopify():
            return getattr(self.adapter, f'get_{entity_name}_metafields_by_id')(entity_id)
        return list()

    def integrationApiImportSaleChannels(self):
        """
        Import sales channels from Shopify.
        """
        if not self.is_shopify():
            return False

        sale_channels = self.adapter.get_sale_channels()

        ctx = dict(default_integration_id=self.id)
        SaleChannel = self.env['external.sale.channel'].with_context(**ctx)
        new_sale_channels = SaleChannel

        # Ensure 'No Channel' exists
        no_channel = SaleChannel._ensure_no_channel_exists(self.id)
        new_sale_channels |= no_channel

        for sale_channel in sale_channels:
            external_id = parse_graphql_id(sale_channel['id'])
            name = sale_channel['name']
            record = SaleChannel.create_or_update(external_id, name)

            new_sale_channels |= record

        # Delete sale channels that don't exist in Shopify
        external_sale_channels = SaleChannel.search([
            ('integration_id', '=', self.id),
        ])
        (external_sale_channels - new_sale_channels).unlink()

        return new_sale_channels

    def _filter_orders_shopify(self, orders_data: list):
        """
        General method to filter Shopify orders.
        This method will find and apply specific Shopify filtering methods.
        """
        initial_count = len(orders_data)

        filtered_orders = self._filter_orders_by_channels(orders_data)

        final_count = len(filtered_orders)
        filtered_out = initial_count - final_count

        _logger.info(
            f'Orders filtered: '
            f'{initial_count} total, {filtered_out} filtered out, {final_count} remaining.'
        )

        return filtered_orders

    def _filter_orders_by_channels(self, orders_data: list):
        """
        Filter orders by channel ID (publication ID).

        This method filters orders based on the integration channels configured.
        It handles the 'No Channel' case for orders without a specific channel.
        """
        external_channel_ids = self.integration_channel_ids.mapped('external_id')

        # Include orders without a channel if 'No Channel' is selected
        include_no_channel = NO_CHANNEL_EXTERNAL_ID in external_channel_ids

        if not external_channel_ids:
            return orders_data

        filtered_orders_data = []
        for order_data in orders_data:
            order = order_data.get('data', {})
            channel_id = parse_graphql_id(order.get('channel_id', ''))

            if channel_id in external_channel_ids or (include_no_channel and not channel_id):
                filtered_orders_data.append(order_data)

        return filtered_orders_data
