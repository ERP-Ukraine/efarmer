# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    fields = env['product.ecommerce.field.mapping'].search([])
    fields.write({'receive_on_import': True})
