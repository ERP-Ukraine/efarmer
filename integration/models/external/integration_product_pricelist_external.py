# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationProductPricelistExternal(models.Model):
    _name = 'integration.product.pricelist.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Pricelist External'
    _odoo_model = 'product.pricelist'

    def _fix_unmapped(self, adapter_external_data):
        result = list()
        mapping_model = self.mapping_model

        for record, adapter_data in zip(self, adapter_external_data):
            mapping = mapping_model.search([
                ('external_pricelist_id', '=', record.id),
                ('integration_id', '=', record.integration_id.id),
            ], limit=1)

            if not mapping:
                continue

            odoo_record = mapping._fix_unmapped_pricelist_one(external_data=adapter_data)
            result.append(odoo_record)

        return result
