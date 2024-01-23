# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    def write(self, vals):
        result = super(ProductTemplateAttributeValue, self).write(vals)
        self.mapped('product_tmpl_id').trigger_export()
        return result
