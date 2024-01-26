from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    Copy default taxes and relation between tax groups and taxes.
    from mapping objects to regular external objects
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    tax_mappings = env['integration.account.tax.mapping']\
        .search([('external_tax_group_id', '!=', False)])
    for tax_mapping in tax_mappings:
        external_tax = tax_mapping.external_tax_id
        external_tax.write(
            {'external_tax_group_ids': [(4, tax_mapping.external_tax_group_id.id, 0)]}
        )

    tax_group_mappings = env['integration.account.tax.group.mapping']\
        .search([('external_tax_id', '!=', False)])
    for tax_group_mapping in tax_group_mappings:
        external_tax_group = tax_group_mapping.external_tax_group_id
        external_tax_group.default_external_tax_id = tax_group_mapping.external_tax_id.id
