#  See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    def to_export_format_gql(self, integration_id: int):
        self.ensure_one()
        return {
            'name': self.attribute_id.get_field_value_in_store_language(integration_id, 'name'),
            'values': [x.to_export_format_gql(integration_id) for x in self.value_ids],
        }
