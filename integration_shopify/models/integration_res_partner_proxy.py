# See LICENSE file for full copyright and licensing details.

import logging

from typing import Dict, List

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class IntegrationResPartnerProxy(models.TransientModel):
    _inherit = 'integration.res.partner.proxy'

    # Fields for customer
    customer_locale = fields.Char(
        string='Customer Locale',
        help='The locale of the customer, e.g., "en-US".',
    )

    def get_proxy_fields(self) -> List:
        """
        Return the list of fields that should be used for the proxy.
        This method is overridden to include 'customer_locale' for Shopify integration.
        """
        fields = super(IntegrationResPartnerProxy, self).get_proxy_fields()
        fields.append('customer_locale')
        return fields

    def _prepare_partner_vals(self) -> Dict:
        """
        Prepare partner values for the integration.
        This method is overridden to ensure that the partner's language is set correctly
        based on the customer locale or integration's  shopify_customer_language.
        """
        vals = super(IntegrationResPartnerProxy, self)._prepare_partner_vals()

        if not self.integration_id.is_shopify():
            return vals

        language = self._get_customer_language()
        if language:
            vals['lang'] = language.code
        else:
            # If no language is found, use the default language from the integration settings
            vals['lang'] = self.integration_id.shopify_customer_language

        return vals

    @api.model
    def _get_customer_language(self):
        """
        Get the Odoo language based on the customer locale.
        If the customer locale is not found in Odoo, log a message.
        """
        language = self.env['res.lang']
        customer_locale = self.customer_locale

        if not customer_locale:
            return language

        # Normalize the customer locale to match Odoo's language codes
        if '-' in customer_locale:
            customer_locale = customer_locale.replace('-', '_')

        language = language.from_external(self.integration_id, customer_locale, False)
        if language:
            return language

        language = language.search([('code', '=', customer_locale)], limit=1)
        if language:
            return language

        _logger.info(
            'Can\'t find customer language (%s) in Odoo. Default customer language from store settings will be used.',
            customer_locale,
        )

        return language

    def _post_update_partner(self, partner: models.Model):
        """
        Update partner fields based on meta field mappings from the integration.
        """
        partner = super(IntegrationResPartnerProxy, self)._post_update_partner(partner)

        if not self.integration_id.is_integration_shopify:
            return partner

        metafield_mappings = self.integration_id.customer_metafield_mapping_ids

        if not metafield_mappings:
            return partner

        # Retrieve meta fields associated with the customer
        customer_metafields = self.integration_id.adapter.get_customer_metafields_by_id(self.external_id)

        if not customer_metafields:
            return partner

        vals = {}
        for mapping in metafield_mappings:

            for customer_metafield in customer_metafields:
                if customer_metafield.get('key') == mapping.metafield_key:
                    metafield_value = customer_metafield.get('value')

                    if mapping.metafield_type == 'boolean':
                        metafield_value = True if metafield_value == 'true' else False

                    vals[mapping.odoo_field_id.name] = metafield_value
                    break

        if vals:
            partner.write(vals)

        return partner
