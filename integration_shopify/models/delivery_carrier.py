# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    shopify_code = fields.Char(
        string='Shopify Code',
    )

    def get_external_carrier_code(self, integration):
        if integration.is_shopify():
            value = self.shopify_code
            if not value:
                raise UserError(_(
                    'The "Shopify Code" field is not defined for the "%s" carrier. You have '
                    'to specify it, so tracking number can be sent from Odoo to Shopify. '
                    'That can be done in the menu "Inventory -> Configuration -> Shipping Methods".'
                ) % self.name)
            return value

        return super(DeliveryCarrier, self).get_external_carrier_code(integration)
