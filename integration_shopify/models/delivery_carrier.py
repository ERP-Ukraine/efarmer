# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError

from ..shopify.resources import (
    SHOPIFY_TRACKING_COMPANY_SELECTION,
    DeliveryMethodType,
    normalize_shopify_tracking_company,
)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    shopify_code = fields.Selection(
        selection=SHOPIFY_TRACKING_COMPANY_SELECTION,
        string='Shopify Code',
        help=(
            'Tracking company name recognized by Shopify. '
            'See: https://shopify.dev/docs/api/admin-graphql/latest/objects/FulfillmentTrackingInfo'
        ),
    )

    integration_send_tracking_url = fields.Boolean(
        string='Send Tracking URL',
        help=(
            'When checkbox is enabled, connector should send tracking URL '
            '(if carrier provides information about the URL).'
        ),
    )

    def get_external_carrier_code(self, integration):
        if integration.is_integration_shopify:
            value = self.shopify_code

            # Switched off for now, the code is still required for every carrier. Pickup and local delivery have
            # no parcel, so there is no tracking company to name, and demanding one blocks the export of such
            # orders. But customers usually map pickup to a default carrier on purpose, so that some code reaches
            # Shopify instead of its own shipping code, and that is the behaviour kept until this is agreed.
            # TODO: acceptable solution but paused
            # if not value and self._is_shopify_non_shipping_method(integration):
            #     return ''

            if not value:
                raise UserError(_(
                    'The "Shopify Code" field is not set for the carrier "%s". Please specify it to '
                    'enable sending the tracking number from Odoo to Shopify. '
                    'You can configure this field in the menu: '
                    '"Inventory → Configuration → Shipping Methods". '
                ) % self.name)

            return value

        return super(DeliveryCarrier, self).get_external_carrier_code(integration)

    def _is_shopify_non_shipping_method(self, integration):
        """Whether the carrier is mapped to a Shopify delivery type other than shipping (pickup, local delivery...).

        Such a method is imported with the delivery type itself as the external code, while a shipping method
        gets a `shopify-shipping-` code (see `DeliveryMethod.to_odoo_format`).
        """
        self.ensure_one()

        external = self.to_external_record(integration, raise_error=False)

        return bool(external) and external.code in DeliveryMethodType.non_shipping_values()

    def _get_carrier_by_external_name(self, integration: 'models.Model', external_name: str):
        if integration.is_integration_shopify:
            shopify_code = normalize_shopify_tracking_company(external_name)

            if shopify_code:
                carrier = self.env['delivery.carrier'].search([
                    ('shopify_code', '=', shopify_code),
                ], limit=1)

                if carrier:
                    return carrier

        return super(DeliveryCarrier, self)._get_carrier_by_external_name(integration, external_name)
