# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductFeatureMapping(models.Model):
    _name = 'integration.product.feature.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Feature Mapping'
    _mapping_fields = ('feature_id', 'external_feature_id')

    feature_id = fields.Many2one(
        comodel_name='product.feature',
        ondelete='cascade',
    )

    external_feature_id = fields.Many2one(
        comodel_name='integration.product.feature.external',
        required=True,
        ondelete='cascade',
    )

    def run_import_features(self):
        external_features = self.mapped('external_feature_id')
        action = external_features.run_import_features()
        return action
