#  See LICENSE file for full copyright and licensing details.

import re

from odoo import models, fields, _

from .fields.send_fields import SendFieldsShopify
from .fields.send_fields_product_product import SendFieldsProductProductShopify
from .fields.send_fields_product_template import SendFieldsProductTemplateShopify
from .fields.receive_fields import ReceiveFieldsShopify
from .fields.receive_fields_product_product import ReceiveFieldsProductProductShopify
from .fields.receive_fields_product_template import ReceiveFieldsProductTemplateShopify

from ..shopify_api import ShopifyAPIClient, SHOPIFY


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

    def is_shopify(self):
        self.ensure_one()
        return self.type_api == SHOPIFY

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
            routes = {
                'orders': [
                    ('Order Create', 'orders/create'),
                    ('Order Paid', 'orders/paid'),
                    ('Order Cancel', 'orders/cancelled'),
                    ('Order Fullfill', 'orders/fulfilled'),
                    ('Order Partially Fullfill', 'orders/partially_fulfilled'),
                ],
            }
            return routes
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
            'integration_shopify.shopify_ecommerce_field_template_weight',
            'integration_shopify.shopify_ecommerce_field_variant_weight',
        ]
