# See LICENSE file for full copyright and licensing details.

from odoo import models


class IrTranslation(models.Model):
    _inherit = 'ir.translation'

    def write(self, vals):
        result = super(IrTranslation, self).write(vals)
        for translation in self:
            model = translation.name.split(',')[0]
            if model != 'product.template':
                continue
            self.env['product.template'].browse(translation.res_id).trigger_export()
        return result
