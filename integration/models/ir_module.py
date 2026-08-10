# See LICENSE file for full copyright and licensing details.

from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo import models, _


INTEGRATION_MODULES = [
    'integration',
    'integration_prestashop',
    'integration_magento2',
    'integration_shopify',
    'integration_woocommerce',
    'integration_baselinker',
    'integration_monitoring',
]


class IrModule(models.Model):
    _inherit = 'ir.module.module'

    @assert_log_admin_access
    def button_immediate_install(self):
        result = super(IrModule, self).button_immediate_install()

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
    def button_immediate_upgrade(self):
        result = super(IrModule, self).button_immediate_upgrade()

        # Open integration installation wizard if the module is an integration module
        # (and it's the only one upgraded)
        if len(self) == 1 and self.name in INTEGRATION_MODULES:
            return self.open_integration_installation_wizard()

        return result
