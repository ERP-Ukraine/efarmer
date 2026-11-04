# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestJobImportButtons(OdooIntegrationInit):
    """Buttons of the failed job form: Open External, Open Mappings and Import External Records.

    The models of a connector are declared in the connector module, so the buttons must find the actions and
    the import by the declaration and never by a list kept in the core.
    """

    def _job(self, model_name):
        return self.env['queue.job'].new({
            'integration_id': self.integration_no_api_1.id,
            'integration_model_name': model_name,
        })

    def test_core_model_has_all_buttons(self):
        job = self._job('integration.account.tax.external')

        self.assertTrue(job.is_open_external_available)
        self.assertTrue(job.is_open_mapping_available)
        self.assertTrue(job.is_import_from_external_available)
        self.assertEqual(job.action_open_external_view()['res_model'], 'integration.account.tax.external')
        self.assertEqual(job.action_open_mapping_view()['res_model'], 'integration.account.tax.mapping')

    def test_import_found_by_entity_declaration(self):
        """Stock locations are not in the list of the core imports, only declared as an import entity."""
        job = self._job('integration.stock.location.external')

        self.assertTrue(job.is_import_from_external_available)
        self.assertTrue(job.is_open_external_available)
        # The model has no mapping, so there is nothing to open
        self.assertFalse(job.is_open_mapping_available)

        with patch.object(type(self.integration_no_api_1), 'integrationApiImportLocations') as import_locations:
            action = job.action_import_from_external_system()

        import_locations.assert_called_once_with()
        self.assertEqual(action['res_model'], 'message.wizard')

    def test_import_is_not_declared_for_model(self):
        """The model has a mapping and an external, but nothing declares how to import it."""
        job = self._job('integration.product.pricelist.external')

        self.assertFalse(job.is_import_from_external_available)
        self.assertTrue(job.is_open_external_available)

        with self.assertRaises(UserError):
            job.action_import_from_external_system()

    def test_unknown_model_has_no_buttons(self):
        job = self._job('integration.not.existing.external')

        self.assertFalse(job.is_import_from_external_available)
        self.assertFalse(job.is_open_external_available)
        self.assertFalse(job.is_open_mapping_available)
        self.assertFalse(job.action_open_external_view())
        self.assertFalse(job.action_open_mapping_view())

    def test_job_without_integration_error_has_no_buttons(self):
        job = self.env['queue.job'].new({})

        self.assertFalse(job.is_import_from_external_available)
        self.assertFalse(job.is_open_external_available)
        self.assertFalse(job.is_open_mapping_available)

    def test_tax_group_is_not_offered_for_import(self):
        """The button used to be shown for the tax groups, but there is no import for them."""
        job = self._job('integration.account.tax.group.external')

        self.assertFalse(job.is_import_from_external_available)
