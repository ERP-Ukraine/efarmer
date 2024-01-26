# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID

NEW_FIELDS = [
    ('shopify_ecommerce_field_template_price', 'shopify_ecommerce_field_variant_price'),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['product.ecommerce.field.mapping'].add_mapping_using_another_field('shopify', NEW_FIELDS)
