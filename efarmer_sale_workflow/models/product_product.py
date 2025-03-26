from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo.tools import config


class ProductProduct(models.Model):
    _inherit = 'product.product'

    description_label = fields.Text(
        string='Description for Product Labels',
        translate=True,
    )

    @api.model
    def create(self, vals):
        product = super().create(vals)
        translations = self.env['ir.translation'].search([
            ('name', '=', 'product.template,description_label'),
            ('type', '=', 'model'),
            ('res_id', '=', product.product_tmpl_id.id),
            ('state', '=', 'translated'),
        ])
        for translation in translations:
            product.with_context(lang=translation.lang).write({"description_label": translation.value})
        return product
