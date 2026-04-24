#  See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _inherit = ['product.attribute.value', 'integration.model.mixin']

    def to_export_format_gql(self, integration_id: int):
        self.ensure_one()
        return {
            'name': self.get_field_value_in_store_language(integration_id, 'name'),
        }

    def to_export_format(self, integration):
        self.ensure_one()

        if integration.is_integration_shopify:
            return {
                'key': self.attribute_id.get_field_value_in_store_language(integration.id, 'name'),
                'value': self.get_field_value_in_store_language(integration.id, 'name'),
                'external_id': self.get_external_code(integration.id),
            }

        return super(ProductAttributeValue, self).to_export_format(integration)

    def export_with_integration(self, integration):
        self.ensure_one()

        if integration.is_integration_shopify:
            return

        return super(ProductAttributeValue, self).export_with_integration(integration)
