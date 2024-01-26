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
            'name': integration.convert_translated_field_to_integration_format(
                self, 'name'
            ),
        }

    def _fill_sequence(self):
        self.ensure_one()

        values_without_sequence = self.value_ids.filtered(lambda v: not v.sequence)
        if not values_without_sequence:
            return

        next_sequence = self._get_next_sequence()
        for rec in values_without_sequence.sorted('id'):
            rec.write({'sequence': next_sequence})
            next_sequence += 1

    @api.constrains('exclude_from_synchronization')
    def _check_product_attribute_values(self):
        for attribute in self.filtered(lambda x: x.exclude_from_synchronization):
            attribute_line = attribute.attribute_line_ids.filtered(lambda l: l.value_count > 1)
            if attribute_line:
                template_names = attribute_line.mapped('product_tmpl_id.display_name')
                raise ValidationError(
                    _('Attribute "%s" cannot be excluded from synchronization as it is used '
                      'in products with more than one value: %s') %
                    (attribute.name, ', '.join(template_names))
                )


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

    def _update_attribute_value_sequence(self):
        for rec in self.mapped('attribute_id'):
            rec._fill_sequence()

    def write(self, vals):
        res = super(ProductTemplateAttributeLine, self).write(vals)
        self._update_attribute_value_sequence()
        return res

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductTemplateAttributeLine, self).create(vals)
        res._update_attribute_value_sequence()
        return res

    @api.constrains('value_ids')
    def _check_exclude_attribute_values(self):
        for record in self.filtered(lambda x: x.exclude_from_synchronization):
            if len(record.value_ids) > 1:
                raise ValidationError(
                    _('Attribute "%s" cannot have multiple values as it is marked as excluded '
                      'from synchronization.') % (record.attribute_id.name,)
                )
