# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductPublicCategory(models.Model):
    _name = 'product.public.category'
    _inherit = ['product.public.category', 'integration.model.mixin']

    def to_export_format(self, integration):
        self.ensure_one()

        if integration.is_shopify():
            return {
                'name': integration.convert_translated_field_to_integration_format(
                    self, 'name'
                ),
            }

        return super(ProductPublicCategory, self).to_export_format(integration)
