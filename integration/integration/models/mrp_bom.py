# See LICENSE file for full copyright and licensing details.

from odoo import models, api


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.model_create_multi
    def create(self, vals_list):
        boms = super(MrpBom, self).create(vals_list)
        boms._trigger_kit_template_export()
        return boms

    def write(self, vals):
        result = super(MrpBom, self).write(vals)
        self._trigger_kit_template_export()
        return result

    def _trigger_kit_template_export(self):
        self.filtered(lambda x: x.type == 'phantom').product_tmpl_id.trigger_export()
