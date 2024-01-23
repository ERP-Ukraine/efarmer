# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, _


class ImportCustomersWizard(models.TransientModel):
    _name = 'import.customers.wizard'
    _description = 'Import Customers Wizard'

    date_since = fields.Datetime(
        string='Import Customers Since',
        required=True,
        default=fields.Datetime.today(),
    )

    @staticmethod
    def _not_defined_from_context():
        return _('Integration may not be defined from context.')

    def _get_sale_integration(self):
        integration = self.env['sale.integration'].browse(self._context.get('active_ids'))

        if len(integration) > 1:
            raise UserError(self._not_defined_from_context())
        elif not integration.exists():
            raise UserError(self._not_defined_from_context())

        return integration

    def run_import(self):
        customers = list()
        integration = self._get_sale_integration()
        limit = integration.get_external_block_limit()
        adapter = integration._build_adapter()
        customer_ids = adapter.get_customer_ids(self.date_since)
        job_kwargs = dict(description='Import Customers: Prepare Customers')

        while customer_ids:
            job = integration.with_delay(**job_kwargs)\
                .run_import_customers_by_blocks(customer_ids[:limit])

            integration.job_log(job)
            customers.append(job)
            customer_ids = customer_ids[limit:]

        return customers
