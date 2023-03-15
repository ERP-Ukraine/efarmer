from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_pl_vat_gtu = fields.Many2one(comodel_name='jpk.gtu')
