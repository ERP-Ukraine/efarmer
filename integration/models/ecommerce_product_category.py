# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class EcommerceProductCategory(models.Model):
    _name = 'ecommerce.product.category'
    _inherit = ['image.mixin', 'integration.model.mixin']
    _description = 'E-Commerce Product Category'
    _parent_store = True
    _order = 'sequence, name, id'

    _internal_reference_field = 'name'

    def _default_sequence(self):
        cat = self.search([], limit=1, order='sequence DESC')
        if cat:
            return cat.sequence + 5
        return 10000

    name = fields.Char(required=True, translate=True)

    parent_id = fields.Many2one(
        comodel_name='ecommerce.product.category',
        string='Parent Category',
        index=True,
        ondelete='cascade',
    )
    child_id = fields.One2many(
        string='Children Categories',
        comodel_name='ecommerce.product.category',
        inverse_name='parent_id',
    )

    parent_path = fields.Char(index=True)

    sequence = fields.Integer(default=_default_sequence, index=True)

    parents_and_self = fields.Many2many(
        comodel_name='ecommerce.product.category',
        compute='_compute_parents_and_self',
    )

    @api.depends('parent_path')
    def _compute_parents_and_self(self):
        for category in self:
            if category.parent_path:
                category.parents_and_self = self.env['ecommerce.product.category'].browse(
                    [int(p) for p in category.parent_path.split('/')[:-1]])
            else:
                category.parents_and_self = category

    @api.depends('parents_and_self')
    def _compute_display_name(self):
        for category in self:
            category.display_name = ' / '.join(category.parents_and_self.mapped(
                lambda cat: cat.name or self.env._('New')
            ))

    @api.constrains('parent_id')
    def check_parent_id(self):
        if self._has_cycle():
            raise ValueError(self.env._('Error! You cannot create recursive categories.'))

    def parse_parent_recursively(self, parents=None):
        parent_list = parents or list()
        parent_list.append(self.id)

        if not self.parent_id:
            return parent_list

        return self.parent_id.parse_parent_recursively(parent_list)

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_category(self)

    def to_export_format(self, integration):
        self.ensure_one()

        parent_id = None
        if self.parent_id:
            parent_id = self.parent_id.to_external_or_export(integration)

        return {
            'parent_id': parent_id,
            'name': self.convert_field_translations_to_external(integration.id, 'name'),
        }
