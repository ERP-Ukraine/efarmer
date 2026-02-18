# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Migration: remove obsolete compare_at_price mappings for Shopify integrations."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    ecommerce_field = env['product.ecommerce.field'].search([
        ('technical_name', '=', 'compare_at_price'),
        ('type_api', '=', 'shopify'),
    ], limit=1)

    if ecommerce_field:
        ecommerce_field.unlink()
