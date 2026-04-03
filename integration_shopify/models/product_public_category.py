# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductPublicCategory(models.Model):
    _name = 'product.public.category'
    _inherit = ['product.public.category', 'integration.model.mixin']

    def to_export_format(self, integration):
        self.ensure_one()

        if integration.is_integration_shopify:
            return {
                'name': self.convert_field_translations_to_external(integration.id, 'name'),
            }

        return super(ProductPublicCategory, self).to_export_format(integration)
