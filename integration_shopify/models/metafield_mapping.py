# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

# Mapping between metafield types and Odoo field types
TYPE_MAPPING = {
    'number_integer': ['integer', 'float', 'char', 'text'],
    'json': ['text'],
    'single_line_text_field': ['char', 'text', 'selection'],
    'boolean': ['boolean'],
    'color': ['char', 'text'],
    'date': ['date', 'char', 'text'],
    'date_time': ['datetime', 'char', 'text'],
    'rich_text_field': ['text'],
    'url': ['char', 'text'],
    'volume': ['char', 'text'],
    'weight': ['char', 'text'],
    'rating': ['char', 'text'],
    'dimension': ['char', 'text'],
    'money': ['char', 'text'],
    'multi_line_text_field': ['char', 'text'],
    'number_decimal': ['float', 'char', 'text'],
    'list.collection_reference': ['char', 'text', 'json'],
    'list.color': ['char', 'text', 'json'],
    'list.date': ['char', 'text', 'json'],
    'list.date_time': ['char', 'text', 'json'],
    'list.dimension': ['char', 'text', 'json'],
    'list.file_reference': ['char', 'text', 'json'],
    'list.metaobject_reference': ['char', 'text', 'json'],
    'list.mixed_reference': ['char', 'text', 'json'],
    'list.number_integer': ['char', 'text', 'json'],
    'list.number_decimal': ['char', 'text', 'json'],
    'list.page_reference': ['char', 'text', 'json'],
    'list.product_reference': ['char', 'text', 'json'],
    'list.rating': ['char', 'text', 'json'],
    'list.single_line_text_field': ['char', 'text', 'json'],
    'list.url': ['char', 'text', 'json'],
    'list.variant_reference': ['char', 'text', 'json'],
    'list.volume': ['char', 'text', 'json'],
    'list.weight': ['char', 'text', 'json'],
}

# Mapping between Shopify object types and Odoo field model
MODEL_MAPPING = {
    'customer': 'res.partner',
    'order': 'sale.order',
}


class Metafield(models.Model):
    _name = 'external.metafield'
    _description = 'Represents the metafields in an external system that can be synced with Odoo'
    _rec_name = 'metafield_name'

    _sql_constraints = [
        (
            'unique_metafield', 'UNIQUE(integration_id, type, metafield_key, metafield_namespace)',
            'A metafield already exists.',
        )
    ]

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        ondelete='cascade',
    )

    type = fields.Selection(
        selection=[
            ('customer', 'Customer'),
            ('order', 'Order'),
        ],
        string='Type',
        help=(
            'Select the type of the metafield. This information is used to map the metafield '
            'to the appropriate Odoo model.'
        ),
    )

    metafield_code = fields.Char(
        string='Code',
        help='This is the unique identifier (gid) of the metafield in the external system.',
    )

    metafield_name = fields.Char(
        string='Metafield Name',
        help='Enter the name of the metafield. This name will be used to identify the metafield in Odoo.',
    )

    metafield_key = fields.Char(
        string='Metafield Key',
        help='This key will be used to reference the metafield in the external system.',
    )

    metafield_namespace = fields.Char(
        string='Namespace',
        help='This is the namespace of the metafield in the external system.',
    )

    metafield_type = fields.Char(
        string='Metafield Type',
        help='This determines the data type of the value that will be stored in the metafield.'
    )


class MetafieldMapping(models.Model):
    _name = 'integration.metafield.mapping'
    _inherits = {'external.metafield': 'metafield_id'}
    _description = 'Mapping between metafields in an external system and fields in Odoo'

    _sql_constraints = [
        (
            'unique_metafield_mapping', 'UNIQUE(metafield_id, odoo_field_id)',
            'A mapping for this metafield already exists with the selected Odoo field.',
        )
    ]

    metafield_id = fields.Many2one(
        comodel_name='external.metafield',
        string='Metafield',
        ondelete='cascade',
        required=True,
        domain="[('integration_id', '=', integration_id)]",
        help=(
            'Select the metafield that you want to map to an Odoo field. The selected metafield '
            'must belong to the same integration as this mapping.'
        ),
    )

    filtered_odoo_fields = fields.Many2many(
        comodel_name='ir.model.fields',
        string='Filtered Odoo Fields',
        compute='_compute_filtered_odoo_fields',
        store=False,
        help=(
            'Technical field used to filter odoo fields based on the metafield type.'
        ),
    )

    odoo_field_id = fields.Many2one(
        string='Odoo Field',
        comodel_name='ir.model.fields',
        domain="[('id', 'in', filtered_odoo_fields)]",
        help=(
            'Select a unique Odoo field for this metafield. Avoid selecting '
            'a field that is already mapped to another metafield in this integration. '
            'You can find existing mappings in the table below.'
        ),
    )

    @api.depends('metafield_id')
    def _compute_filtered_odoo_fields(self):
        for mapping in self:
            field_type_mapping = TYPE_MAPPING.get(mapping.metafield_type)
            if field_type_mapping:
                model_name = MODEL_MAPPING.get(mapping.metafield_id.type)
                odoo_fields = self.env['ir.model.fields'].search([
                    ('model', '=', model_name),
                    ('ttype', 'in', field_type_mapping),
                ])
                mapping.filtered_odoo_fields = odoo_fields
            else:
                mapping.filtered_odoo_fields = False
