# See LICENSE file for full copyright and licensing details.

from typing import List, Dict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.sql import escape_psql

import logging

_logger = logging.getLogger(__name__)


class IntegrationEcommerceProductCategoryExternal(models.Model):
    _name = 'integration.ecommerce.product.category.external'
    _inherit = 'integration.external.mixin'
    _description = 'E-Commerce Product Category External'
    _rec_name = 'complete_name'
    _order = 'complete_name'
    _odoo_model = 'ecommerce.product.category'
    _map_field = 'name'

    parent_id = fields.Many2one(
        comodel_name=_name,
        string='Parent Category',
        ondelete='cascade',
    )
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            name = category.name

            if category.parent_id:
                name = f'{category.parent_id.complete_name} / {name}'

            category.complete_name = name

    def _post_import_external_multi(self, adapter_external_records):
        adapter_router = {str(x['id']): x for x in adapter_external_records}
        self_router = {x.code: x for x in self}

        for rec in self:
            adapter_record = adapter_router.get(rec.code, dict())
            parent_id = adapter_record.get('id_parent')

            if parent_id:
                external_parent_record = self_router.get(parent_id, False)
                rec.parent_id = external_parent_record

    def try_map_by_external_reference(self, odoo_search_domain=False):
        self.ensure_one()

        # If we found existing mapping, we do not need to do anything
        odoo_record = self.odoo_record
        if odoo_record:
            return odoo_record

        self.create_or_update_mapping()

        # Find similar Odoo category by name
        odoo_record = self._find_similar_odoo_category()

        if odoo_record:
            self.create_or_update_mapping(odoo_id=odoo_record.id)

        return self.odoo_record

    def import_categories(self):
        integrations = self.mapped('integration_id')

        for integration in integrations:
            # Import categories from E-Commerce System
            external_categories_data = integration.adapter.get_categories()

            for category in self.filtered(lambda x: x.integration_id == integration):
                category.import_category(external_categories_data)

    def import_category(self, external_categories_data: List[Dict]):
        self.ensure_one()

        if self.mapping_record and self.mapping_record.category_id:
            # If mapping exists, we do not need to do anything
            # This means that the category was already imported or manually mapped
            # It is too risky to update the category name because mapping could be created manually
            return

        # If mapping doesn`t exists try to find category by the name
        odoo_category = self._find_similar_odoo_category()

        if odoo_category:
            self.create_or_update_mapping(odoo_id=odoo_category.id)

            # Update category name including translations
            external_category_data = [c for c in external_categories_data if c['id'] == self.code]  # NOQA
            if not external_category_data:
                raise UserError(_(
                    'No category found in the external system with code "%s" (%s). '
                    'Please verify that the category exists and is correctly imported.'
                ) % (self.code, self.name))

            external_category_data = external_category_data[0]
            name = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(self.integration_id.id, external_category_data['name'])

            odoo_category = self.create_or_update_with_translations(
                self.integration_id.id,
                odoo_category,
                {'name': name},
            )

            # There is nothing else to do
            return

        # If we didn't find category by name, we need to create it
        # This includes creating parent categories, excluding categories that already exist
        # So, we need to prepare the list of categories to create, starting from the root
        category_path = [self]
        current_category = self
        while current_category.parent_id:
            category_path.insert(0, current_category.parent_id)
            current_category = current_category.parent_id

        # Create categories
        parent = None
        for category in category_path:
            odoo_category = category._find_similar_odoo_category()

            if odoo_category:
                # If we found the category in the path, we do not need to update it because
                # most likely it was updated during the its import or should be update by separate
                # import process
                # Why? To avoid redundant database updates during import because it parent category
                # has 10 children, we will update the category 10 times!

                parent = odoo_category

                continue

            external_category_data = [c for c in external_categories_data if c['id'] == category.code]  # NOQA

            if not external_category_data:
                raise UserError(_(
                    'No category found in the external system with code "%s" (%s). '
                    'Please verify that the category exists and is correctly imported.'
                ) % (self.code, self.name))

            external_category_data = external_category_data[0]
            name = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(self.integration_id.id, external_category_data['name'])

            odoo_category = self.create_or_update_with_translations(
                self.integration_id.id,
                odoo_category,
                {'name': name},
            )

            category.create_or_update_mapping(odoo_id=odoo_category.id)

            if odoo_category.parent_id:
                if odoo_category.parent_id == parent:
                    # This is case when category already existed and was found by name
                    pass
                else:
                    # This case should never happen, but it is better to check
                    raise UserError(_(
                        'The category "%s" already exists but is linked to a different parent category. '
                        'Please review the category hierarchy and update the parent category if necessary.'
                    ) % category.name)
            else:
                # This is case when category was created and we need to set its parent
                odoo_category.parent_id = parent

            # We have to explicitly call the method to update the parents_and_self field
            # Otherwise, we won't be able to get correct categories path in the next iteration
            # and will get duplicated categories
            odoo_category._compute_parents_and_self()

            parent = odoo_category

    def _find_similar_odoo_category(self):
        odoo_categories = self.odoo_model.search([
            ('name', '=ilike', escape_psql(self.name)),
        ])

        def calculate_complete_name(category):
            return ' / '.join(category.parents_and_self.mapped('name'))

        # If found by name, check if it is a child of the parent category
        odoo_category = odoo_categories.filtered(
            lambda c: calculate_complete_name(c) == self.complete_name
        )

        if len(odoo_category) > 1:
            raise UserError(_(
                f'Multiple e-commerce categories with the name "{self.name}" were found. Please ensure that category '
                'names are unique to avoid conflicts.'
            ))

        return odoo_category

    def _map_external(self, adapter_external_data):
        cycle_category_id = self.find_loop_category(adapter_external_data)
        if cycle_category_id:
            raise UserError(_(
                'A loop was detected in the product category hierarchy. Please review the '
                'parent-child relationships of the categories. The category with ID %s is causing the loop.'
            ) % cycle_category_id)

        return super(IntegrationEcommerceProductCategoryExternal, self)._map_external(adapter_external_data)

    @staticmethod
    def find_loop_category(categories):
        categories_dict = {
            category['id']: category
            for category in categories if 'id_parent' in category
        }

        def find_loop(category, stack):
            if category in stack:
                return stack[stack.index(category):]
            stack.append(category)
            if category['id_parent'] in categories_dict:
                parent = categories_dict[category['id_parent']]
                result = find_loop(parent, stack)
                if result:
                    return result
            stack.pop()
            return []

        for category in categories_dict.values():
            cycle = find_loop(category, [])
            if cycle:
                return cycle[0].get('id')

        return None
