# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductEcommerceFieldMapping(models.Model):
    _inherit = 'product.ecommerce.field.mapping'

    def get_translation_key(self, field_name_only: bool = True):
        self.ensure_one()
        return self.ecommerce_field_id.get_translation_key(field_name_only=field_name_only)

    def has_translatable_fields(self, integration_id: int, add_domain: list = None):
        domain = [
            ('active', '=', True),
            ('is_translatable_field', '=', True),
            ('integration_id', '=', integration_id),
            *add_domain,
        ]
        return self.search_count(domain) > 0
