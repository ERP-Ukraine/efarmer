# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductFeature(models.Model):
    _name = 'product.feature'
    _inherit = ['integration.model.mixin']
    _description = 'Product Feature'
    _order = 'sequence, id'
    _internal_reference_field = 'name'

    name = fields.Char(string='Feature', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', help="Determine the display order", index=True)
    value_ids = fields.One2many(
        comodel_name='product.feature.value',
        inverse_name='feature_id',
        string='Values',
        copy=True
    )

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_feature(self)

    def to_export_format(self, integration):
        self.ensure_one()

        return {
            'name': integration.convert_translated_field_to_integration_format(self, 'name'),
        }
