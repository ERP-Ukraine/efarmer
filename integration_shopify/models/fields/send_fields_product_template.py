# See LICENSE file for full copyright and licensing details.

from odoo.addons.integration.models.fields import ProductTemplateSendMixin

from .send_fields import SendFieldsShopify


class SendFieldsProductTemplateShopify(SendFieldsShopify, ProductTemplateSendMixin):

    def convert_pricelists(self, *args, **kw):
        raise NotImplementedError

    def send_integration_name(self, field_name):
        return {
            field_name: self.odoo_obj.get_integration_name(self.integration),
        }

    def send_product_status_spf(self, field_name):
        if not self.odoo_obj.active:
            return {field_name: 'archived'}
        send_inactive_product = not self.external_id and self.integration.send_inactive_product
        if send_inactive_product or not self.odoo_obj.sale_ok:
            return {field_name: 'draft'}
        return {field_name: 'active'}

    def send_categories(self, field_name):
        return {
            field_name: self.odoo_obj.get_categories(self.integration),
        }

    def send_list_price(self, field_name):
        return {}

    def send_product_tags(self, field_name):
        features = self.odoo_obj.get_product_features(self.integration)
        tags = ','.join([x['id_feature_value'] for x in features])
        return {
            field_name: tags,
        }
