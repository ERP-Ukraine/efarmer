# See LICENSE file for full copyright and licensing details.

from odoo import models


class ECommerceProductCategory(models.Model):
    _name = 'ecommerce.product.category'
    _inherit = ['ecommerce.product.category', 'integration.model.mixin']

    def to_export_format(self, integration):
        self.ensure_one()

        if integration.is_integration_shopify:
            return {
                'name': self.name,
            }

        return super(ECommerceProductCategory, self).to_export_format(integration)
