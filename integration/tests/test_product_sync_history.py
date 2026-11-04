# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_product_sync_history')
class TestProductSyncHistory(OdooIntegrationInit):

    def _history(self, record):
        action = record.open_related_jobs()
        return self.env['queue.job'].search(action['domain'])

    def test_stock_export_job_in_product_history(self):
        integration = self.integration_no_api_1
        variant_1 = self.product_pt_1.product_variant_ids
        variant_2 = self.product_pt_2.product_variant_ids

        # "Export Stock to Stores" and the scheduled export link the job to the variants of the batch only
        job_1 = variant_1.export_inventory_by_jobs(integration)[0].db_record()
        job_2 = variant_2.export_inventory_by_jobs(integration)[0].db_record()

        self.assertIn(job_1, self._history(self.product_pt_1))
        self.assertIn(job_1, self._history(variant_1))
        self.assertNotIn(job_2, self._history(self.product_pt_1))
        self.assertNotIn(job_1, self._history(self.product_pt_2))
        self.assertIn(job_2, self._history(variant_2))

    def test_template_jobs_stay_in_product_history(self):
        # The real-time stock export links its jobs to the template, as the product export does
        job = self.product_pt_1._export_inventory_on_template(self.integration_no_api_1.id)[0].db_record()

        self.assertIn(job, self._history(self.product_pt_1))
        self.assertNotIn(job, self._history(self.product_pt_2))
