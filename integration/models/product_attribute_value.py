# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _inherit = ['product.attribute.value', 'integration.model.mixin']
    _internal_reference_field = 'name'

    exclude_from_synchronization = fields.Boolean(
        related='attribute_id.exclude_from_synchronization',
    )

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductAttributeValue, self).create(vals)

        # If the sequence is not set, we must set it to the next available sequence
        # We can't use simple check like "not r.sequence" because sequence will be 0 by default, so
        # we won't know if the user set it to 0 or if it's the default value
        for (r, v) in list(zip(res, vals)):
            if v.get('sequence') is None:
                next_sequence = r.attribute_id._get_next_sequence()
                r.write({'sequence': next_sequence})

        return res

    def to_export_format(self, integration):
        self.ensure_one()

        attribute = self.attribute_id.to_external_or_export(integration)
        name = self.convert_field_translations_to_external(integration.id, 'name')

        return {
            'name': name,
            'attribute': attribute,
            'external_id': self.get_external_code(integration.id),
        }

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_attribute_value(self)
