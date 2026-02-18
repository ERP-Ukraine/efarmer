# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationECommerceProductCategoryMapping(models.Model):
    _name = 'integration.ecommerce.product.category.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'E-Commerce Product Category Mapping'
    _mapping_fields = ('category_id', 'external_category_id')

    category_id = fields.Many2one(
        string='Odoo E-Commerce Category',
        comodel_name='ecommerce.product.category',
        ondelete='cascade',
    )

    external_category_id = fields.Many2one(
        string='External E-Commerce Category',
        comodel_name='integration.ecommerce.product.category.external',
        required=True,
        ondelete='cascade',
    )

    # TODO: Add constraint

    def import_categories(self):
        category_external = self.mapped(
            'external_category_id'
        )

        if category_external:
            return category_external.import_categories()
