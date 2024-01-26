# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

import logging

_logger = logging.getLogger(__name__)


class IntegrationProductFeatureValueExternal(models.Model):
    _name = 'integration.product.feature.value.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Feature Value External'
    _odoo_model = 'product.feature.value'

    external_feature_id = fields.Many2one(
        comodel_name='integration.product.feature.external',
        string='External Feature',
        readonly=True,
        ondelete='cascade',
    )

    def _fix_unmapped(self, adapter_external_data):
        self._fix_unmapped_element(self.integration_id, 'feature')

        # After importing new feature values, we need to re-check all mapped features
        # to make sure that there is no new unmapped values for them
        self._fix_unmapped_element_values(self.integration_id, 'feature')

    def _post_import_external_one(self, adapter_external_record):
        self._post_import_external_element(adapter_external_record, 'feature')

    def _pre_import_external_check(self, external_record, integration):
        """
        This method will check possibility to import Feature Value
        """
        if not external_record.get('id_group'):
            return True

        external_element = self.env['integration.product.feature.external'].search([
            ('code', '=', external_record.get('id_group')),
            ('integration_id', '=', integration.id),
        ])

        return bool(external_element)
