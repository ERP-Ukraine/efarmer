# See LICENSE file for full copyright and licensing details.

from typing import Dict

from odoo import api, models


class IntegrationSaleOrderFactory(models.AbstractModel):
    _inherit = 'integration.sale.order.factory'

    @api.model
    def _prepare_order_vals(self, integration, order_data):
        res = super(IntegrationSaleOrderFactory, self)\
            ._prepare_order_vals(integration, order_data)

        if integration.is_shopify():
            external_location_id = order_data.get('external_location_id')

            if external_location_id:
                warehouse = integration._get_wh_from_external_location(external_location_id)
                if warehouse:
                    res['warehouse_id'] = warehouse.id

            channel_id = order_data.get('channel_id')
            if channel_id:
                # Check if the user has imported sales channels.
                # This is to avoid issues with order imports after migrating
                # from old versions to 1.17.0 (when sales channels were introduced).
                # Before version 1.17.0, the connector didn't require the 'read_publications'
                # permission, which is now needed for importing sales channels.
                if self.env['external.sale.channel'].search([('integration_id', '=', integration.id)]):
                    sale_channel = self.env['external.sale.channel'].get_record(integration.id, channel_id)
                    res['integration_sale_channel_id'] = sale_channel.id if sale_channel else False

        return res

    def _prepare_order_line_vals(self, integration, line):
        res = super(IntegrationSaleOrderFactory, self)._prepare_order_line_vals(integration, line)

        if integration.is_shopify():
            external_location_id = line.get('external_location_id')

            if external_location_id:
                warehouse = integration._get_wh_from_external_location(external_location_id)
                if warehouse:
                    res['warehouse_id'] = warehouse.id

        return res

    def _post_create_order(self, integration: models.Model, order: models.Model, order_data: Dict):
        """
        Update order fields based on meta field mappings from the integration.
        """
        super(IntegrationSaleOrderFactory, self)._post_create_order(integration, order, order_data)

        if not integration.is_shopify():
            return order

        metafield_mappings = integration.order_metafield_mapping_ids

        if not metafield_mappings:
            return order

        # Retrieve meta fields associated with the order
        order_metafields = integration.get_object_metafields('order', order_data['id'])

        if not order_metafields:
            return order

        vals = {}
        for mapping in metafield_mappings:

            for order_metafield in order_metafields:
                if order_metafield.get('key') == mapping.metafield_key:
                    metafield_value = order_metafield.get('value')

                    if mapping.metafield_type == 'boolean':
                        metafield_value = True if metafield_value == 'true' else False

                    vals[mapping.odoo_field_id.name] = metafield_value
                    break

        if vals:
            order.write(vals)

        return order
