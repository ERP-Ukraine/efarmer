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
        """
        Returns a message indicating that the integration cannot be determined from the context.
        """
        return _(
            'Technical Error: The integration could not be identified from the current context.\n\n'
            'This issue is likely due to a misconfiguration or missing context information.\n\n'
            'Please contact our support team at https://support.ventor.tech and provide details about '
            'the operation you were performing when this error occurred.'
        )

    def _get_sale_integration(self):
        integration = self.env['sale.integration'].browse(self.env.context.get('active_ids'))

        if len(integration) > 1:
            raise UserError(self._not_defined_from_context())
        elif not integration.exists():
            raise UserError(self._not_defined_from_context())

        return integration

    def run_import(self):
        integration = self._get_sale_integration()
        integration = integration.with_context(company_id=integration.company_id.id)
        limit = integration.get_external_block_limit()

        customer_ids = integration.adapter.get_customer_ids(self.date_since)

        job_kwargs = dict(
            priority=3,
            description='Import Customers: Prepare Customers',
        )

        result = []
        while customer_ids:
            job = integration \
                .with_delay(**job_kwargs) \
                .run_import_customers_by_blocks(customer_ids[:limit])

            integration.job_log(job)
            result.append(job)
            customer_ids = customer_ids[limit:]

        return result
