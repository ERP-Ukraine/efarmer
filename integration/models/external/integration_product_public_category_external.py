# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.sql import escape_psql

import logging

_logger = logging.getLogger(__name__)


class IntegrationProductPublicCategoryExternal(models.Model):
    _name = 'integration.product.public.category.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Public Category External'
    _rec_name = 'complete_name'
    _order = 'complete_name'
    _odoo_model = 'product.public.category'
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

    def _fix_unmapped(self, adapter_external_data):
        ProductPublicCategory = self.odoo_model

        if ProductPublicCategory.search([]):
            return

        category_mappings = []
        integration = self.integration_id
        external_values = integration._build_adapter().get_categories()

        # Create categories
        for external_value in external_values:
            external_product_category = self.get_external_by_code(
                integration,
                external_value['id'],
                raise_error=False,
            )

            name = integration.convert_translated_field_to_odoo_format(external_value['name'])

            category = self.create_or_update_with_translation(
                integration=integration,
                odoo_object=ProductPublicCategory,
                vals={'name': name},
            )

            category_mappings.append(
                external_product_category.create_or_update_mapping(odoo_id=category.id)
            )
        # Create tree
        category_by_code = {}

        category_by_code.update({
            x.external_public_category_id.code: x.public_category_id
            for x in category_mappings
        })

        # in case we only receive 1 record its not added to list as others
        if not isinstance(external_values, list):
            external_values = [external_values]

        for ext_category in external_values:
            parent_id = ext_category.get('id_parent', None)
            category = category_by_code.get(ext_category['id'], None)
            if category and parent_id:
                if not category.parent_id:
                    category.parent_id = category_by_code.get(parent_id, None)

    def import_categories(self):
        integrations = self.mapped('integration_id')

        for integration in integrations:
            # Import categories from e-Commerce System
            external_values = integration._build_adapter().get_categories()

            for category in self.filtered(lambda x: x.integration_id == integration):
                category.import_category(external_values)

    def import_category(self, external_values):
        self.ensure_one()

        ProductCategory = self.odoo_model
        MappingCategory = self.mapping_model

        # Try to find existing and mapped category
        mapping = MappingCategory.search([
            ('external_public_category_id', '=', self.id),
        ])

        # If mapping doesn`t exists try to find category by the name
        if not mapping or not mapping.public_category_id:
            self._check_similar_in_odoo()
            odoo_category = ProductCategory.browse()
        else:
            assert len(mapping) == 1, _('Expected one mapping to one external record.')
            odoo_category = mapping.public_category_id

        # in case we only receive 1 record its not added to list as others
        if not isinstance(external_values, list):
            external_values = [external_values]

        # Find category in external and children of our category
        external_value = [x for x in external_values if x['id'] == self.code]
        external_children = [x for x in external_values if x.get('id_parent') == self.code]

        if external_value:
            external_value = external_value[0]
            name = self.integration_id.convert_translated_field_to_odoo_format(
                external_value['name'])

            odoo_category = self.create_or_update_with_translation(
                integration=self.integration_id,
                odoo_object=odoo_category,
                vals={'name': name},
            )

            self.create_or_update_mapping(odoo_id=odoo_category.id)

            # Set parent of our category
            if external_value.get('id_parent'):
                parent_mapping = MappingCategory.get_mapping(
                    self.integration_id,
                    external_value['id_parent']
                )

                if parent_mapping and parent_mapping.public_category_id:
                    odoo_category.parent_id = parent_mapping.public_category_id

            # Find children and set parent to them
            for external_child in external_children:
                child_mapping = MappingCategory.get_mapping(
                    self.integration_id,
                    external_child['id']
                )

                if child_mapping and child_mapping.public_category_id:
                    child_mapping.public_category_id.parent_id = odoo_category

    def _check_similar_in_odoo(self):
        odoo_category = self.odoo_model.search([
            ('name', '=ilike', escape_psql(self.name)),
        ])

        if odoo_category:
            external_complete_name = self.complete_name
            odoo_category_records = odoo_category.browse()

            for category in odoo_category:
                odoo_parent_path = '/ '.join(category.parents_and_self.mapped('name'))

                if odoo_parent_path == external_complete_name:
                    odoo_category_records |= category

            if len(odoo_category_records) == 1:
                message = _('Public category with name "%s" already exists') % self.name
            elif len(odoo_category_records) > 1:
                message = _('There are several public categories with name "%s"') % self.name
            else:
                message = False

            if message:
                raise UserError(message)

    def _map_external(self, adapter_external_data):
        cycle_category_id = self.find_loop_category(adapter_external_data)
        if cycle_category_id:
            raise UserError(
                _('The product categories contain a loop. Please check the parent-child '
                  'relationships of the categories. Category with id %s is causing the loop.') %
                cycle_category_id
            )

        return super(IntegrationProductPublicCategoryExternal, self)._map_external(
            adapter_external_data)

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
