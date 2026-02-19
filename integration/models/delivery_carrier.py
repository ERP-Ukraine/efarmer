# See LICENSE file for full copyright and licensing details.

from odoo import models


class DeliveryCarrier(models.Model):
    _name = 'delivery.carrier'
    _inherit = ['delivery.carrier', 'integration.model.mixin']
    _internal_reference_field = 'name'

    def get_external_carrier_code(self, integration):
        return self.to_external(integration)

    def _get_carrier_by_external_name(self, integration, external_name):
        return self.env['delivery.carrier'].search([
            ('name', '=', external_name),
        ], limit=1)
