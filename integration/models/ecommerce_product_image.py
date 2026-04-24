# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class EcommerceProductImage(models.Model):
    _name = 'ecommerce.product.image'
    _description = 'E-Commerce Product Image'
    _inherit = ['image.mixin', 'integration.image.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)

    sequence = fields.Integer(default=10)

    image_1920 = fields.Image(required=True)

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        index=True,
        ondelete='cascade',
    )

    product_variant_id = fields.Many2one(
        comodel_name='product.product',
        string='Product Variant',
        index=True,
        ondelete='cascade',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Skip default_product_tmpl_id from context when product_variant_id is set
        to prevent variant images from appearing as template images.
        """
        context_without_template = self.with_context({
            k: v for k, v in self.env.context.items()
            if k != 'default_product_tmpl_id'
        })
        normal_vals = []
        variant_vals_list = []

        for vals in vals_list:
            if vals.get('product_variant_id') and 'default_product_tmpl_id' in self.env.context:
                variant_vals_list.append(vals)
            else:
                normal_vals.append(vals)

        return super().create(normal_vals) + \
            super(EcommerceProductImage, context_without_template).create(variant_vals_list)
