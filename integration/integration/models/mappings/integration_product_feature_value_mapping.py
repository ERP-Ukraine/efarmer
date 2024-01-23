# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductFeatureValueMapping(models.Model):
    _name = 'integration.product.feature.value.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Feature Value Mapping'
    _mapping_fields = ('feature_value_id', 'external_feature_value_id')

    feature_value_id = fields.Many2one(
        comodel_name='product.feature.value',
        ondelete='cascade',
    )

    external_feature_value_id = fields.Many2one(
        comodel_name='integration.product.feature.value.external',
        required=True,
        ondelete='cascade',
    )

    feature_id = fields.Many2one(
        comodel_name='product.feature',
        compute='_compute_feature_id',
    )

    def get_feature_id(self):
        self.ensure_one()
        external_feature_id = self.external_feature_value_id.external_feature_id
        return self.env['product.feature'].from_external(
            self.integration_id, external_feature_id.code, False)

    def _compute_feature_id(self):
        for value in self:
            value.feature_id = value.get_feature_id()
