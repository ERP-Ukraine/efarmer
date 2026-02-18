# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _name = 'product.attribute'
    _inherit = ['product.attribute', 'integration.model.mixin']
    _internal_reference_field = 'name'

    exclude_from_synchronization = fields.Boolean(
        string='Exclude from Synchronization',
        help='Exclude from synchronization with external systems. '
             'It means that attribute will not be exported to external systems.',
    )

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_attribute(self)

    def to_export_format(self, integration):
        self.ensure_one()

        return {
            'id': self.id,
            'name': self.convert_field_translations_to_external(integration.id, 'name'),
        }

    @api.constrains('exclude_from_synchronization')
    def _check_product_attribute_values(self):
        for attribute in self.filtered(lambda x: x.exclude_from_synchronization):
            attribute_line = attribute.attribute_line_ids.filtered(lambda line: line.value_count > 1)
            if attribute_line:
                template_names = attribute_line.mapped('product_tmpl_id.display_name')
                raise ValidationError(_(
                    'The attribute "%s" cannot be excluded from synchronization because it is used in products '
                    'that have more than one value.\n\n'
                    'This attribute is used in the following product templates:\n%s'
                ) % (attribute.name, ', '.join(template_names)))

    def _get_next_sequence(self):
        sequence_list = self.value_ids.mapped('sequence')
        return max(sequence_list, default=0) + 1


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    exclude_from_synchronization = fields.Boolean(
        related='attribute_id.exclude_from_synchronization',
        readonly=True,
    )

    is_dynamic_creation_mode = fields.Boolean(
        string='Dynamic Creation Mode Variants',
        compute='_compute_dynamic_creation_mode',
        help='Dynamic variant creation mode is enabled.',
    )

    def _compute_dynamic_creation_mode(self):
        for line in self:
            line.is_dynamic_creation_mode = line.attribute_id.create_variant == 'dynamic'

    @api.constrains('value_ids')
    def _check_exclude_attribute_values(self):
        for record in self.filtered(lambda x: x.exclude_from_synchronization):
            if len(record.value_ids) > 1:
                raise ValidationError(_(
                    'The attribute "%s" cannot have multiple values because it is marked as excluded '
                    'from synchronization.\n\n'
                    'Please ensure that attributes marked for exclusion only have a single value.'
                ) % (record.attribute_id.name,))
