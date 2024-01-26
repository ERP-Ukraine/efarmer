# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    integrations = env['sale.integration'].search([])
    field_api = env['sale.integration.api.field']

    for rec in integrations:
        if 'decimal_precision' not in rec.mapped('field_ids.name'):
            decimal_precision = rec.company_id.currency_id.decimal_places or '2'
            new_field_api = field_api.create({
                'name': 'decimal_precision',
                'description': 'Number of decimal places in the price of the exported product',
                'value': decimal_precision,
            })
            rec.field_ids |= new_field_api
