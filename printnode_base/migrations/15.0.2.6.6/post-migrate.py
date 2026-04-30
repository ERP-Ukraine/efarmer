from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    accounts = env['printnode.account'].with_context(active_test=False).search([
        ('endpoint', '!=', False),
    ])

    for account in accounts:
        normalized = account.endpoint.rstrip('/')
        if account.endpoint != normalized:
            account.write({'endpoint': normalized})
