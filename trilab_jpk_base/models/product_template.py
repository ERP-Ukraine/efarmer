from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_pl_vat_gtu = fields.Many2one('jpk.gtu', 'JPK GTU', tracking=True, export_string_translation=False)

    x_pl_vat_mpp = fields.Boolean(
        'MPP',
        help='Indicates that any product variants based on this template should be treated under the split payment '
        'mechanism (MPP) criteria when invoicing.',
        export_string_translation=False,
    )
