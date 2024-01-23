# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    code = env['res.users'].browse(SUPERUSER_ID).lang or env.lang or 'en_US'

    lang = env['res.lang'].with_context(active_test=False).search([
        ('code', '=', code),
    ])

    for integration in env['sale.integration'].search([]):
        integration.write({
            'integration_lang_id': lang.id,
        })
