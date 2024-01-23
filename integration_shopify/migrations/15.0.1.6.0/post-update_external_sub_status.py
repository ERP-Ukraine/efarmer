# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    integrations = env['sale.integration'].search([
        ('type_api', '=', 'shopify'),
    ])

    SubStatus = env['integration.sale.order.sub.status.external']
    # 0. Drop records with code 'unfulfilled'
    records_unfulfilled = SubStatus.search([
        ('code', '=', 'unfulfilled'),
        ('integration_id', 'in', integrations.ids),
    ])
    records_unfulfilled.unlink()

    # 1. Update the records with code `null`
    records_null = SubStatus.search([
        ('code', '=', 'null'),
        ('integration_id', 'in', integrations.ids),
    ])
    vals = dict(
        code='unfulfilled',
        name='Unfulfilled',
    )
    records_null.write(vals)

    for rec in records_null:
        erp_id = rec.mapping_model.to_odoo(rec.integration_id, rec.code, False)
        erp_id.name = rec.name

    # 2. Update the records with code `unpaid`
    records_unpaid = SubStatus.search([
        ('code', '=', 'unpaid'),
        ('integration_id', 'in', integrations.ids),
    ])
    vals = dict(
        name='Unpaid',
    )
    records_unpaid.write(vals)

    for rec in records_unpaid:
        mapping = rec.mapping_model._search_mapping_from_external(
            rec.integration_id,
            rec,
        )
        mapping.unlink()

    # 3. Re import sub-statuses
    wizard = env['configuration.wizard.shopify'].search([])
    wizard.unlink()

    for int_id in integrations:
        int_id = int_id.with_context(company_id=int_id.company_id.id)

        job = int_id.with_delay(
            description=f'{int_id.name}: Re-Import. Sub-Statuses',
        ).integrationApiImportSaleOrderStatuses()

        int_id.job_log(job)
