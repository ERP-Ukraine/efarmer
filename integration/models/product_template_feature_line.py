# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplateFeatureLine(models.Model):
    _name = 'product.template.feature.line'
    _description = 'Feature Line'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        index=True
    )
    feature_id = fields.Many2one(
        comodel_name='product.feature',
        string='Feature',
        ondelete='cascade',
        required=True,
    )
    feature_value_id = fields.Many2one(
        comodel_name='product.feature.value',
        string='Value',
        ondelete='cascade',
        required=True,
        domain="[('feature_id', '=', feature_id)]"
    )

    @api.constrains('feature_id', 'feature_value_id')
    def check_matching_feature_id(self):
        for record in self:
            if record.feature_id != record.feature_value_id.feature_id:
                raise ValidationError(_(
                    'The selected Feature Value ("%s") does not belong to the Feature ("%s"). Please select a '
                    'matching Feature Value.'
                ) % (record.feature_value_id.name, record.feature_id.name))
