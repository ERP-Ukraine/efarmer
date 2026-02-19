# See LICENSE file for full copyright and licensing details.

from typing import Dict

from odoo import api, models


class IntegrationSaleOrderFactory(models.AbstractModel):
    _inherit = 'integration.sale.order.factory'

    @api.model
    def _prepare_order_vals(self, integration, order_data):
        res = super(IntegrationSaleOrderFactory, self) \
            ._prepare_order_vals(integration, order_data)

        if integration.is_integration_shopify:
            # 1. Prepare warehouse
            external_location_id = order_data['external_location_id']
            if external_location_id:
                warehouse = integration._get_wh_from_external_location(external_location_id)
                if warehouse:
                    res['warehouse_id'] = warehouse.id

            # 2. Prepare sale channel
            channel_data = order_data['sale_channel_data']
            if channel_data:
                channel = self.env['external.sale.channel'].create_or_update(
                    integration.id,
                    channel_data['channel_id'],
                    channel_data['channel_name']
                )

                res['integration_sale_channel_id'] = channel.id

            # 3. Prepare order source name
            source_name = order_data['order_source_name']
            if source_name:
                order_source_name = self.env['external.order.source.name'] \
                    .get_or_create(integration.id, source_name)

                res['integration_order_source_name_id'] = order_source_name.id

        return res

    def _prepare_order_line_vals(self, integration, line):
        res = super(IntegrationSaleOrderFactory, self)._prepare_order_line_vals(integration, line)

        if integration.is_integration_shopify:
            external_location_id = line.get('external_location_id')

            if external_location_id:
                warehouse = integration._get_wh_from_external_location(external_location_id)
                if warehouse:
                    res['warehouse_id'] = warehouse.id

        return res

    @api.model
    def _create_order(self, integration, order_data):
        """
        Override to create a sale order.
        """
        order = super(IntegrationSaleOrderFactory, self)._create_order(integration, order_data)

        if integration.is_integration_shopify:
            payment_methods = self.env['sale.order.payment.method']
            for payment_method_data in order_data['payment_methods']:
                payment_methods |= self._get_payment_method(integration, payment_method_data)

            if payment_methods:
                order.write({
                    'payment_method_ids': [(6, 0, payment_methods.ids)],
                })

        return order

    def _post_create_order(self, integration: models.Model, order: models.Model, order_data: Dict):
        """
        Update order fields based on meta field mappings from the integration.
        """
        super(IntegrationSaleOrderFactory, self)._post_create_order(integration, order, order_data)

        if not integration.is_integration_shopify:
            return order

        metafield_mappings = integration.order_metafield_mapping_ids

        if not metafield_mappings:
            return order

        # Retrieve meta fields associated with the order
        order_metafields = integration.adapter.get_order_metafields_by_id(order_data['id'])

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
