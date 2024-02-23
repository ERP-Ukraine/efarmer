# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationProductFeatureExternal(models.Model):
    _name = 'integration.product.feature.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Feature External'
    _odoo_model = 'product.feature'
    _map_field = 'name'

    external_feature_value_ids = fields.One2many(
        comodel_name='integration.product.feature.value.external',
        inverse_name='external_feature_id',
        string='External Feature Values',
        readonly=True,
    )

    def run_import_features(self):
        action = self._run_import_elements_element('feature')
        return action
