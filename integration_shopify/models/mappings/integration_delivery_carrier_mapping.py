# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationDeliveryCarrierMapping(models.Model):
    _inherit = 'integration.delivery.carrier.mapping'

    shopify_code = fields.Selection(
        string='Shopify Code',
        related='carrier_id.shopify_code',
        readonly=False,
    )
