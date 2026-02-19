# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_integration_cost_price(self, integration_id: int):
        self.ensure_one()
        if self.product_tmpl_id.product_variant_count > 1:
            return self.standard_price
        return self.product_tmpl_id.standard_price

    def to_export_format(self, integration):
        result = super().to_export_format(integration)

        if integration.is_integration_shopify:
            # Update external_id
            external_id = result['external_id']
            if external_id:
                adapter = integration.adapter
                value = adapter.gql.ProductVariant.create_gid(external_id.rsplit('-', 1)[-1])
            else:
                value = external_id

            result['gid'] = value

            # Update attribute_values to match Shopify format
            attribute_values = result.pop('attribute_values', False) or []
            result['attribute_values'] = [{'optionName': x['key'], 'name': x['value']} for x in attribute_values]

        return result
