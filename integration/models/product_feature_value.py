# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError


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

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductFeatureValue, self).create(vals)

        # If the sequence is not set, we must set it to the next available sequence
        # We can't use simple check like "not r.sequence" because sequence will be 0 by default, so
        # we won't know if the user set it to 0 or if it's the default value
        for (r, v) in list(zip(res, vals)):
            if v.get('sequence') is None:
                next_sequence = r.feature_id._get_next_sequence()
                r.write({'sequence': next_sequence})

        return res

    def to_export_format(self, integration):
        self.ensure_one()

        feature_code = self.feature_id.to_external_or_export(integration)

        if not self.feature_id:
            raise UserError(_(
                'The external feature code cannot be empty for the feature value "%s".\n\n'
            ) % self.name)

        return {
            'feature_id': feature_code,
            'name': self.convert_field_translations_to_external(integration.id, 'name'),
        }

    def export_with_integration(self, integration):
        self.ensure_one()
        return integration.export_feature_value(self)
