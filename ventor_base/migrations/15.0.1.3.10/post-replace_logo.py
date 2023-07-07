# Odoo:
from odoo import api, SUPERUSER_ID


def migrate(cr, version):

    env = api.Environment(cr, SUPERUSER_ID, {})
    company_ids = env['res.company'].with_context(active_test=False).search([])

    cr.execute("""SELECT value FROM ventor_config WHERE key = 'logo.file';""")
    values = env.cr.dictfetchall()
    
    logotype_file = False
    for item in values:
        if item.get('value'):
            logotype_file = item.get('value')
            break
    company_ids.logotype_file = logotype_file
