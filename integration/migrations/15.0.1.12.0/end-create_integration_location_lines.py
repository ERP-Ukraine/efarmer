# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    StockLocationLine = env['external.stock.location.line']
    integrations = env['sale.integration'].search([])

    for int_id in integrations:
        locations = int_id.location_ids
        if not locations:
            continue

        def prepare_vals(rec):
            return dict(integration_id=int_id.id, erp_location_id=rec.id)

        vals_list = [prepare_vals(x) for x in locations]
        StockLocationLine.create(vals_list)
