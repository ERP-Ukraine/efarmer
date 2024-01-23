# See LICENSE file for full copyright and licensing details.

from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo import models
from ..patch import SKIP_CLS


class IrModule(models.Model):
    _inherit = 'ir.module.module'

    def _upgrade_integration(self):
        if any(self.env.ref('base.module_' + module_name) in self for module_name in SKIP_CLS):
            self.env.ref('base.module_integration').button_immediate_upgrade()

    @assert_log_admin_access
    def button_immediate_install(self):
        result = super(IrModule, self).button_immediate_install()

        self._upgrade_integration()

        return result

    @assert_log_admin_access
    def button_immediate_uninstall(self):
        result = super(IrModule, self).button_immediate_uninstall()

        self._upgrade_integration()

        return result
