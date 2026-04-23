from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_pl_vat_gtu = fields.Many2one(comodel_name='jpk.gtu', string='JPK GTU', tracking=True)

    x_pl_vat_mpp = fields.Boolean(
        string='MPP',
        help='Indicates that any product variants based on this template should be treated under the split payment '
        'mechanism (MPP) criteria when invoicing.',
    )
