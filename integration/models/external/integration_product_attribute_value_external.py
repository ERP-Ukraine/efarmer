# See LICENSE file for full copyright and licensing details.

from odoo import models, fields

import logging

_logger = logging.getLogger(__name__)


class IntegrationProductAttributeValueExternal(models.Model):
    _name = 'integration.product.attribute.value.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Attribute Value External'
    _odoo_model = 'product.attribute.value'

    external_attribute_id = fields.Many2one(
        comodel_name='integration.product.attribute.external',
        string='External Attribute',
        readonly=True,
        ondelete='cascade',
    )

    def _fix_unmapped(self, adapter_external_data):
        self._fix_unmapped_element(self.integration_id, 'attribute')

        # After importing new feature values, we need to re-check all mapped features
        # to make sure that there is no new unmapped values for them
        self._fix_unmapped_element_values(self.integration_id, 'attribute')

    def _post_import_external_one(self, adapter_external_record):
        self._post_import_external_element(adapter_external_record, 'attribute')
