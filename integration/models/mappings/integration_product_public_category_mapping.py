# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductPublicCategoryMapping(models.Model):
    _name = 'integration.product.public.category.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Public Category Mapping'
    _mapping_fields = ('public_category_id', 'external_public_category_id')

    public_category_id = fields.Many2one(
        comodel_name='product.public.category',
        ondelete='cascade',
    )

    external_public_category_id = fields.Many2one(
        comodel_name='integration.product.public.category.external',
        required=True,
        ondelete='cascade',
    )

    # TODO: Add constraint

    def import_categories(self):
        category_external = self.mapped(
            'external_public_category_id'
        )

        if category_external:
            return category_external.import_categories()
