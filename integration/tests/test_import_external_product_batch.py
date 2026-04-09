# See LICENSE file for full copyright and licensing details.

import uuid
from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.addons.integration.exceptions import ErrorStore as es

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install')
class TestImportExternalProductBatch(OdooIntegrationInit):

    def test_import_external_product_all_failed_raises_error(self):
        """Raises UserError when all imports fail."""
        error_list = ['Error 1', 'Error 2']
        template_ids = ['EXT-001', 'EXT-002']

        env = self.env

        def mock_import(integration_self, tpl_ids, **kwargs):
            return (
                env['integration.product.template.external'].browse(),
                env['integration.product.product.external'].browse(),
                error_list,
                template_ids
            )
        self.patch(type(self.integration_no_api_1), '_import_external_product', mock_import)

        with self.assertRaises(es.UserError) as cm:
            self.integration_no_api_1.import_external_product(template_ids)

        self.assertIn('No external products found or imported', str(cm.exception))
        self.assertIn('Error 1', str(cm.exception))
        self.assertIn('Error 2', str(cm.exception))

    def test_import_external_product_partial_success_returns_message(self):
        """Returns success message when some imports succeed."""
        error_list = ['Error when trying to auto-match']
        failed_ids = ['EXT-002']

        external_pt = self.external_pt_1
        external_var = self.external_pt_1_var

        def mock_import(integration_self, tpl_ids, **kwargs):
            return (external_pt, external_var, error_list, failed_ids)

        self.patch(type(self.integration_no_api_1), '_import_external_product', mock_import)

        result = self.integration_no_api_1.import_external_product(['EXT-001', 'EXT-002'])

        self.assertIn('Import (partial) completed successfully', result)
        self.assertIn('Errors when importing products', result)

    def test_import_external_product_partial_errors_creates_retry_job(self):
        """Creates retry job when there are partial errors (with job_uuid context)."""
        job_uuid = str(uuid.uuid4())

        self.env.cr.execute("""
            INSERT INTO queue_job (uuid, name, model_name, method_name, state, date_created, priority)
            VALUES (%s, 'Test Job', 'sale.integration', 'import_external_product', 'started', NOW(), 10)
        """, (job_uuid,))

        error_list = ['Error when trying to auto-match']
        failed_ids = ['EXT-002']

        external_pt = self.external_pt_1
        external_var = self.external_pt_1_var

        def mock_import(integration_self, tpl_ids, **kwargs):
            return (external_pt, external_var, error_list, failed_ids)

        self.patch(type(self.integration_no_api_1), '_import_external_product', mock_import)

        mock_delayable = MagicMock()
        mock_delayable.import_external_product.return_value = MagicMock()
        self.patch(type(self.integration_no_api_1), 'with_delay', lambda self, **kw: mock_delayable)

        result = self.integration_no_api_1.with_context(job_uuid=job_uuid).import_external_product(
            ['EXT-001', 'EXT-002'],
        )

        self.assertIn('moved in separate job', result)
        mock_delayable.import_external_product.assert_called_once_with(['EXT-002'])
