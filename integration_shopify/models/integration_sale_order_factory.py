# See LICENSE file for full copyright and licensing details.

from typing import Dict

from odoo import fields, models


class IntegrationSaleOrderFactory(models.TransientModel):
    _inherit = 'integration.sale.order.factory'

    external_order_financial_status = fields.Char(
        string='External Financial Status',
    )

    external_order_fulfillment_status = fields.Char(
        string='External Fulfillment Status',
    )

    @property
    def workflow_states(self):
        if self.integration_id.is_integration_shopify:
            return [x for x in [
                self.external_order_financial_status,
                self.external_order_fulfillment_status,
            ] if x]
        return super().workflow_states

    def _extract_workflow_data(self, order_data):
        super()._extract_workflow_data(order_data)
        if self.integration_id.is_integration_shopify:
            states = order_data.get('integration_workflow_states', [])
            self.external_order_financial_status = states[0] if states else False
            self.external_order_fulfillment_status = states[1] if len(states) > 1 else False

    def _prepare_order_vals(self, order_data):
        integration = self.integration_id
        res = super(IntegrationSaleOrderFactory, self)._prepare_order_vals(order_data)

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

    def _prepare_order_line_vals(self, order, line_data):
        integration = self.integration_id
        res = super(IntegrationSaleOrderFactory, self)._prepare_order_line_vals(order, line_data)

        if integration.is_integration_shopify:
            external_location_id = line_data.get('external_location_id')

            if external_location_id:
                warehouse = integration._get_wh_from_external_location(external_location_id)
                if warehouse:
                    res['warehouse_id'] = warehouse.id

        return res

    def _create_order(self, order_data):
        """
        Override to create a sale order.
        """
        integration = self.integration_id
        order = super(IntegrationSaleOrderFactory, self)._create_order(order_data)

        if integration.is_integration_shopify:
            payment_methods = self.env['sale.order.payment.method']
            for payment_method_data in order_data['payment_methods']:
                payment_methods |= self._get_payment_method(payment_method_data)

            if payment_methods:
                order.write({
                    'payment_method_ids': [(6, 0, payment_methods.ids)],
                })

        return order

    def _post_create_order(self, order: models.Model, order_data: Dict):
        """
        Update order fields based on meta field mappings from the integration.
        """
        integration = self.integration_id
        super(IntegrationSaleOrderFactory, self)._post_create_order(order, order_data)

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
