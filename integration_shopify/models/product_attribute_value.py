#  See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _inherit = ['product.attribute.value', 'integration.model.mixin']

    def to_export_format(self, integration):
        self.ensure_one()

        if integration.is_shopify():
            return {
                'key': integration.convert_translated_field_to_integration_format(
                    self.attribute_id, 'name',
                ),
                'value': integration.convert_translated_field_to_integration_format(
                    self, 'name',
                ),
                'external_id': self.try_to_external(integration),
            }

        return super(ProductAttributeValue, self).to_export_format(integration)

    def export_with_integration(self, integration):
        self.ensure_one()

        if integration.is_shopify():
            return

        return super(ProductAttributeValue, self).export_with_integration(integration)
