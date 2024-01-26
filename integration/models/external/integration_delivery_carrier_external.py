# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationDeliveryCarrierExternal(models.Model):
    _name = 'integration.delivery.carrier.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Delivery Carrier External'
    _odoo_model = 'delivery.carrier'

    def _fix_unmapped(self, adapter_external_data):
        mappings = self.mapping_model.search([
            ('external_carrier_id', 'in', self.ids),
            ('integration_id', '=', self.integration_id.id),
        ])
        return mappings._fix_unmapped_shipping_multi()
