# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools import config
from odoo.tools.config import DEFAULT_SERVER_WIDE_MODULES


CONNECTORS = [
    'integration_baselinker',
    'integration_magento2',
    'integration_prestashop',
    'integration_shopify',
    'integration_woocommerce',
]


@tagged('post_install', '-at_install')
class TestInstallationWizardServerWide(TransactionCase):
    """Which modules the configuration check asks to load as server-wide."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Module = cls.env['ir.module.module']
        cls.wizard = cls.env['integration.installation.wizard'].create({})
        # An installed module named like a connector that is not one: an extension or a customization.
        cls.extension = cls.Module.create({'name': 'integration_custom_extra', 'state': 'installed'})

    def _required(self) -> list:
        connectors = self.Module.search([('name', 'in', CONNECTORS), ('state', '=', 'installed')])
        return DEFAULT_SERVER_WIDE_MODULES + ['integration', 'integration_queue_job'] + connectors.mapped('name')

    def _check(self, server_wide_modules: list) -> tuple:
        with patch.dict(config.options, {'server_wide_modules': server_wide_modules}):
            errors, modules_str = self.wizard._check_server_wide_modules()

        return errors, modules_str.split(',')

    def test_all_required_modules_present(self):
        errors, modules = self._check(self._required())

        self.assertFalse(errors)
        self.assertEqual(sorted(modules), sorted(self._required()))

    def test_installed_module_that_is_not_a_connector_is_not_required(self):
        errors, modules = self._check(self._required())

        self.assertFalse(errors)
        self.assertNotIn(self.extension.name, modules)

    def test_missing_installed_connector_is_required(self):
        connector = self.Module.search([('name', '=', 'integration_shopify')])
        connector.state = 'installed'
        server_wide = [x for x in self._required() if x != connector.name]

        errors, modules = self._check(server_wide)

        self.assertTrue(errors)
        self.assertIn(connector.name, modules)

    def test_connector_that_is_not_installed_is_not_required(self):
        connector = self.Module.search([('name', '=', 'integration_magento2')])
        connector.state = 'uninstalled'
        server_wide = self._required()

        errors, modules = self._check(server_wide)

        self.assertNotIn(connector.name, server_wide)
        self.assertFalse(errors)
        self.assertNotIn(connector.name, modules)

    def test_extra_module_already_listed_is_kept(self):
        # Admins who followed the old hint have an extension listed; a working config must not need editing back.
        errors, modules = self._check(self._required() + [self.extension.name])

        self.assertFalse(errors)
        self.assertIn(self.extension.name, modules)
