# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationResPartnerProxy(models.TransientModel):
    _inherit = 'integration.res.partner.proxy'
    _description = 'Integration Res Partner Proxy'

    def _post_update_partner(self, partner: models.Model):
        """
        Update partner fields based on meta field mappings from the integration.
        """
        partner = super(IntegrationResPartnerProxy, self)._post_update_partner(partner)

        if not self.integration_id.is_shopify():
            return partner

        metafield_mappings = self.integration_id.customer_metafield_mapping_ids

        if not metafield_mappings:
            return partner

        # Retrieve meta fields associated with the customer
        customer_metafields = self.integration_id.get_object_metafields('customer', self.external_id)

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
