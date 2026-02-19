# See LICENSE file for full copyright and licensing details.

from odoo.addons.base.models.ir_module import assert_log_admin_access
from odoo import models


class IrModule(models.Model):
    _inherit = 'ir.module.module'

    @assert_log_admin_access
    def button_immediate_uninstall(self):
        result = super(IrModule, self).button_immediate_uninstall()
        self._set_quality_check_per_product_line()
        return result

    @assert_log_admin_access
    def button_immediate_install(self):
        result = super(IrModule, self).button_immediate_install()
        self._set_quality_check_per_product_line()
        return result

    def _set_quality_check_per_product_line(self):
        for module in self:
            if module.name == 'quality_control':
                stock_picking_type_ids = self.env['stock.picking.type'].with_context(active_test=False).search([])
                ventor_quality_control_settings = self.env['ventor.option.setting'].search(
                        [
                            ('technical_name', '=', 'quality_check_per_product_line'),
                        ]
                    )
                if module.state == 'installed':
                    stock_picking_type_ids.quality_check_per_product_line = True
                    ventor_quality_control_settings.value = self.env.ref('ventor_base.bool_true')
                elif module.state == 'uninstalled':
                    stock_picking_type_ids.quality_check_per_product_line = False
                    ventor_quality_control_settings.value = self.env.ref('ventor_base.bool_false')
