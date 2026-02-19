# See LICENSE file for full copyright and licensing details.

from odoo import models, api


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(MrpBomLine, self).create(vals_list)
        lines.bom_id._trigger_bom_template_export()
        return lines

    def write(self, vals):
        result = super(MrpBomLine, self).write(vals)
        self.bom_id._trigger_bom_template_export()

        if 'product_qty' in vals:
            self.bom_id._triger_bom_inventory_export()

        return result
