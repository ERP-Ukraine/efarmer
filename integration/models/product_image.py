# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


# This model used without website_sale module
class ProductImage(models.Model):
    _name = 'product.image'
    _description = 'Product Image'
    _inherit = ['image.mixin', 'integration.image.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        required=True,
    )

    sequence = fields.Integer(
        default=10,
        index=True,
    )

    image_1920 = fields.Image(
        required=True,
    )

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

    video_url = fields.Char(
        string='Video URL',
        help='URL of a video for showcasing your product.',
    )


# This model used with website_sale module
# and is needed to avoid deleting data when deleting website_sale module
class ProductImageInherit(models.Model):
    _name = 'product.image'
    _inherit = ['product.image', 'integration.image.mixin']

    name = fields.Char(
        required=True,
    )

    sequence = fields.Integer(
        default=10,
        index=True,
    )

    image_1920 = fields.Image(
        required=True,
    )

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

    video_url = fields.Char(
        string='Video URL',
        help='URL of a video for showcasing your product.',
    )
