# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductAttributeMapping(models.Model):
    _name = 'integration.product.attribute.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Attribute Mapping'
    _mapping_fields = ('attribute_id', 'external_attribute_id')

    attribute_id = fields.Many2one(
        comodel_name='product.attribute',
        ondelete='cascade',
    )

    external_attribute_id = fields.Many2one(
        comodel_name='integration.product.attribute.external',
        required=True,
        ondelete='cascade',
    )

    def run_import_attributes(self):
        external_attributes = self.mapped('external_attribute_id')
        action = external_attributes.run_import_attributes()
        return action
