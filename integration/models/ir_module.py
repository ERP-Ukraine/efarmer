# See LICENSE file for full copyright and licensing details.

from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo import models, _


MODULES_TO_TRIGGER_INTEGRATION_UPGRADE = [
    'mrp',
    'website_sale',
]

INTEGRATION_MODULES = [
    'integration',
    'integration_prestashop',
    'integration_magento2',
    'integration_shopify',
    'integration_woocommerce',
    'integration_monitoring',
]


class IrModule(models.Model):
    _inherit = 'ir.module.module'

    def _upgrade_integration(self):
        # Trigger integration upgrade if any of the following modules are installed or uninstalled
        module_refs = [
            self.env.ref('base.module_' + module_name)
            for module_name in MODULES_TO_TRIGGER_INTEGRATION_UPGRADE
        ]
        if any(module_ref in self for module_ref in module_refs):
            self.env.ref('base.module_integration').button_immediate_upgrade()

    @assert_log_admin_access
    def button_immediate_install(self):
        result = super(IrModule, self).button_immediate_install()

        self._upgrade_integration()

        # Open integration installation wizard if the module is an integration module
        # (and it's the only one installed)
        if len(self) == 1 and self.name in INTEGRATION_MODULES:
            return self.open_integration_installation_wizard()

        return result

    def open_integration_installation_wizard(self):
        wizard = self.env['integration.installation.wizard'].create({})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Let\'s ensure a seamless setup!'),
            'res_model': 'integration.installation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @assert_log_admin_access
    def button_immediate_uninstall(self):
        result = super(IrModule, self).button_immediate_uninstall()

        self._upgrade_integration()

        return result

    @assert_log_admin_access
    def button_immediate_upgrade(self):
        result = super(IrModule, self).button_immediate_upgrade()

        # Open integration installation wizard if the module is an integration module
        # (and it's the only one upgraded)
        if len(self) == 1 and self.name in INTEGRATION_MODULES:
            return self.open_integration_installation_wizard()

        return result
