# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    integrations = env['sale.integration'].search([])
    integrations.update_crons_activity()

    parameter = env['ir.config_parameter'].search([('key', '=', 'integration.data_block_size')])

    if parameter:
        parameter.key = 'integration.import_data_block_size'
