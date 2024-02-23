# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductAttributeValueMapping(models.Model):
    _name = 'integration.product.attribute.value.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Attribute Value Mapping'
    _mapping_fields = ('attribute_value_id', 'external_attribute_value_id')

    attribute_value_id = fields.Many2one(
        comodel_name='product.attribute.value',
        ondelete='cascade',
    )

    external_attribute_value_id = fields.Many2one(
        comodel_name='integration.product.attribute.value.external',
        required=True,
        ondelete='cascade',
    )

    attribute_id = fields.Many2one(
        comodel_name='product.attribute',
        compute='_compute_attribute_id',
    )

    def get_attribute_id(self):
        self.ensure_one()
        external_attribute_id = self.external_attribute_value_id.external_attribute_id
        return self.env['product.attribute'].from_external(
            self.integration_id, external_attribute_id.code, False)

    def _compute_attribute_id(self):
        for value in self:
            value.attribute_id = value.get_attribute_id()
