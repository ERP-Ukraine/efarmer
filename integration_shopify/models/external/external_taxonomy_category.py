# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.addons.integration.exceptions import ErrorStore as es


class ExternalTaxonomyCategory(models.Model):
    _name = 'external.taxonomy.category'
    _inherit = 'integration.external.mixin'
    _description = 'E-Commerce Product Taxonomy Category'
    _order = 'level, parent_id, name'
    _rec_name = 'complete_name'
    _parent_store = True

    parent_id = fields.Many2one(
        comodel_name='external.taxonomy.category',
        string='Parent Category',
        ondelete='cascade',
    )

    parent_path = fields.Char(index=True)

    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
    )

    is_archived = fields.Boolean(
        string='Archived',
        default=False,
    )

    level = fields.Integer(
        string='Level',
        default=0,
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.complete_name or rec.name or rec.code

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            name = category.name or ''

            if category.parent_id:
                parent_name = category.parent_id.complete_name or category.parent_id.name or ''
                name = f'{parent_name} / {name}'

            category.complete_name = name

    def _post_import_external_multi(self, adapter_external_records):
        external_data_by_code = {x['id']: x for x in adapter_external_records}
        records_by_code = {x.code: x for x in self}

        # Sort by API-returned level so parents are processed before children
        sorted_records = sorted(
            self,
            key=lambda r: (external_data_by_code.get(r.code, {}).get('level') or 0),
        )

        for rec in sorted_records:
            data = external_data_by_code.get(rec.code, {})
            vals = {}

            level = data.get('level')
            if level is not None:
                vals['level'] = level

            is_archived = data.get('is_archived')
            if is_archived is not None:
                vals['is_archived'] = is_archived

            parent_code = data.get('id_parent')
            if parent_code:
                parent = records_by_code.get(parent_code)
                if parent:
                    vals['parent_id'] = parent.id

            if vals:
                rec.write(vals)

    @api.model
    def find_category(self, category_data, raise_if_not_found: bool = False):
        category = self.search([
            ('code', '=', category_data['id']),
        ], limit=1)

        if not category and raise_if_not_found:
            raise es.NoExternal(
                _(
                    'Taxonomy Category "%s" (code: %s) not found.\n'
                    'Please import Master Data or run "Import Taxonomy Categories" '
                    'from the integration Testing tab first.'
                ) % (category_data['name'], category_data['id'])
            )

        return category
