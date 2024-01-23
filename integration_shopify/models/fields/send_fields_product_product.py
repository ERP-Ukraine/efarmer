# See LICENSE file for full copyright and licensing details.

from .send_fields import SendFieldsShopify
from ...shopify_api import VARIANT
from odoo.addons.integration.models.fields import ProductProductSendMixin


class SendFieldsProductProductShopify(SendFieldsShopify, ProductProductSendMixin):

    def send_lst_price(self, field_name):
        if self.integration.integration_pricelist_id:
            price = self.integration.integration_pricelist_id.get_product_price(
                self.odoo_obj, 0, False,
            )
        else:
            price = self.odoo_obj.lst_price
        return {
            field_name: self.get_price_by_send_tax_incl(price),
        }

    def send_integration_cost_price(self, field_name):
        return {
            field_name: self.odoo_obj.get_integration_cost_price(self.integration),
        }

    def send_weight(self, field_name):
        shopify_uom = None

        if self.external_id:
            shopify_variant_id = self.adapter._parse_variant_id(self.external_id)
            variant = self.adapter.fetch_one(VARIANT, shopify_variant_id, fields=['weight_unit'])
            if not variant.is_new():
                shopify_uom = variant.weight_unit

        if not shopify_uom:
            shopify_uom = self.adapter.get_weight_uom_for_converter()

        weight = self.convert_weight_uom_from_odoo(self.odoo_obj.weight, shopify_uom)
        return {
            field_name: weight,
        }

    def send_taxable_flag(self, field_name):
        return {
            field_name: bool(self.odoo_obj.product_tmpl_id.taxes_id),
        }
