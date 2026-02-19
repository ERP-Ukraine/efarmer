# See LICENSE file for full copyright and licensing details.

from odoo import models, api


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.model_create_multi
    def create(self, vals_list):
        boms = super(MrpBom, self).create(vals_list)
        boms._trigger_bom_template_export()
        return boms

    def write(self, vals):
        result = super(MrpBom, self).write(vals)
        self._trigger_bom_template_export()

        if 'product_qty' in vals:
            self._triger_bom_inventory_export()

        return result

    def _trigger_bom_template_export(self):
        self.product_tmpl_id.trigger_export()

    def _triger_bom_inventory_export(self):
        template = self.product_tmpl_id
        integrations = template.mapped('product_variant_ids.integration_ids').filtered(lambda x: x.is_active)
        for integration in integrations:
            template._export_inventory_on_template(integration.id)
