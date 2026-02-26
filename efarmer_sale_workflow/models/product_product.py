from odoo import  models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    description_label = fields.Text(
        string='Description for Product Labels',
        translate=True,
    )
