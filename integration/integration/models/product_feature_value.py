# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductFeatureValue(models.Model):
    _name = 'product.feature.value'
    _inherit = ['integration.model.mixin']
    _description = 'Feature Value'
    _order = 'feature_id, sequence, id'
    _internal_reference_field = 'name'

    name = fields.Char(string='Value', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', help="Determine the display order", index=True)
    feature_id = fields.Many2one(
        comodel_name='product.feature',
        string='Feature',
        ondelete='cascade',
        required=True,
        index=True,
    )

    def to_export_format(self, integration):
        self.ensure_one()

        return {
            'feature_id': self.feature_id.to_external_or_export(integration),
            'name': integration.convert_translated_field_to_integration_format(self, 'name'),
        }

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_feature_value(self)
