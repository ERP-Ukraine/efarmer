# See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import UserError
from odoo.addons.integration.models.fields import ProductProductReceiveMixin

from .receive_fields import ReceiveFieldsShopify
from ...shopify.shopify_client import INVENT_ITEM


class ReceiveFieldsProductProductShopify(ReceiveFieldsShopify, ProductProductReceiveMixin):

    def __init__(self, integration, odoo_obj=False, external_obj=False):
        super().__init__(integration, odoo_obj, external_obj)

        if external_obj:
            self.product = self.external_obj[0]
            self.variant = self.external_obj[1]

        if not self.odoo_obj:
            self.odoo_obj = self.env['product.product']

    def get_ext_attr(self, ext_attr_name):
        if ext_attr_name == 'variant_id':
            return f'{self.product.id}-{self.variant.id}'
        if ext_attr_name == 'attribute_value_ids':
            template_attribute_ids = self.adapter._attribute_value_from_template(self.product)
            return self.adapter._attribute_value_from_variant(self.variant, template_attribute_ids)

        raise UserError(_('Import attribute "%s" do not exist') % ext_attr_name)

    def _get_value(self, field_name):
        return getattr(self.variant, field_name, None)

    def receive_lst_price(self, field_name):
        if len(self.product.variants) == 1:
            return {field_name: 0}

        price = float(self.variant.price)  # TODO price_including_taxes

        extra_price = price - (self.odoo_obj.lst_price - self.odoo_obj.variant_extra_price)
        return {
            field_name: extra_price,
        }

    def receive_integration_cost_price(self, field_name):
        if self.variant.inventory_item_id:
            inventory_item = self.adapter.fetch_one(INVENT_ITEM, self.variant.inventory_item_id)

            return {
                field_name: inventory_item.cost and float(inventory_item.cost) or 0,
            }

        return {}

    def receive_weight(self, field_name):
        weight = float(self.variant.weight or 0)
        weight = self.convert_weight_uom_to_odoo(weight, self.variant.weight_unit)

        return {
            field_name: weight,
        }

    def receive_taxable_flag(self, field_name):
        taxable_flag = any([v.taxable for v in self.product.variants])

        if not taxable_flag:
            return {
                field_name: False,
            }
        return {}
