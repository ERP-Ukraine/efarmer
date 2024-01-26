# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationProductAttributeExternal(models.Model):
    _name = 'integration.product.attribute.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Attribute External'
    _odoo_model = 'product.attribute'
    _map_field = 'name'

    external_attribute_value_ids = fields.One2many(
        comodel_name='integration.product.attribute.value.external',
        inverse_name='external_attribute_id',
        string='External Attribute Values',
        readonly=True,
    )

    def run_import_attributes(self):
        action = self._run_import_elements_element('attribute', link_to_existing=True)
        return action

    def _get_mode_create_variant(self, *args, **kw):
        if self.integration_id.is_import_dynamic_attribute:
            return 'dynamic'
        return 'always'
