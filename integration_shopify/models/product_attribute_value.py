#  See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.integration.exceptions import ErrorStore as es


class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _inherit = ['product.attribute.value', 'integration.model.mixin']

    def to_export_format(self, integration):
        self.ensure_one()

        if not integration.is_integration_shopify:
            return super(ProductAttributeValue, self).to_export_format(integration)

        try:
            attribute_name = self.attribute_id.to_external_record(integration).name
        except es.NotMappedToExternal:
            attribute_name = self.attribute_id.get_field_value_in_store_language(integration.id, 'name')

        try:
            value_name = self.to_external_record(integration).name
        except es.NotMappedToExternal:
            value_name = self.get_field_value_in_store_language(integration.id, 'name')

        return {
            'key': attribute_name,
            'value': value_name,
            'external_id': self.get_external_code(integration.id),
        }

    def export_with_integration(self, integration):
        self.ensure_one()

        if integration.is_integration_shopify:
            return

        return super(ProductAttributeValue, self).export_with_integration(integration)
