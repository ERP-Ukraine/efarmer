# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields


class ProductVariantReplacementWizard(models.TransientModel):
    _name = 'product.variant.replacement.wizard'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Current Product',
        readonly=True,
    )

    replacement_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Replacement Product',
        domain='[("product_tmpl_id", "=", product_tmpl_id)]',
    )

    sale_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        readonly=True
    )

    def apply_replacement(self):
        if self.replacement_product_id:
            self.sale_line_id.product_id = self.replacement_product_id.id
