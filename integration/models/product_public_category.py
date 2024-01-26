# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductPublicCategoryMixin(models.AbstractModel):
    _name = 'product.public.category.mixin'
    _inherit = 'integration.model.mixin'
    _description = 'Mixin Website Product Category'

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_category(self)

    def to_export_format(self, integration):
        self.ensure_one()

        parent_id = None
        if self.parent_id:
            parent_id = self.parent_id.to_external_or_export(integration)

        name = integration.convert_translated_field_to_integration_format(self, 'name')

        return {
            'name': name,
            'parent_id': parent_id,
        }

    def parse_parent_recursively(self, parents=None):
        parent_list = parents or list()
        parent_list.append(self.id)

        if not self.parent_id:
            return parent_list

        return self.parent_id.parse_parent_recursively(parent_list)


# This model used without website_sale module
class ProductPublicCategory(models.Model):
    _name = 'product.public.category'
    _inherit = ['image.mixin', 'product.public.category.mixin']
    _description = 'Website Product Category'
    _parent_store = True
    _order = 'sequence, name'
    _internal_reference_field = 'name'

    name = fields.Char(
        required=True,
        translate=True,
    )

    parent_id = fields.Many2one(
        comodel_name='product.public.category',
        string='Parent Category',
        index=True,
    )

    parent_path = fields.Char(
        index=True,
    )

    sequence = fields.Integer(
        index=True,
    )

    parents_and_self = fields.Many2many(
        'product.public.category',
        compute='_compute_parents_and_self'
    )

    def name_get(self):
        res = []
        for category in self:
            res.append((category.id, ' / '.join(category.parents_and_self.mapped('name'))))
        return res

    def _compute_parents_and_self(self):
        for category in self:
            if category.parent_path:
                category.parents_and_self = self.env['product.public.category'].browse(
                    [int(p) for p in category.parent_path.split('/')[:-1]])
            else:
                category.parents_and_self = category


# This model used with website_sale module
# and is needed to avoid deleting data when deleting website_sale module
class ProductPublicCategoryInherit(models.Model):
    _name = 'product.public.category'
    _inherit = ['product.public.category', 'product.public.category.mixin']
    _internal_reference_field = 'name'

    name = fields.Char()
    parent_id = fields.Many2one()
    parent_path = fields.Char()
    sequence = fields.Integer()
