# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Update integration mapping fields
    for integration in env['sale.integration'].search([]):
        integration.write_settings_fields()
        integration._update_crons_activity()

        integration.create_fields_mapping_for_integration()

        if integration.is_active:
            integration.set_settings_value('access_granted', 'True')

        if integration.is_integration_shopify:
            # 1.1 Disable OAuth for Shopify
            integration.set_settings_value('use_oauth', 'False')

            # 1.2 Migrate the receive_order_fulfillment_statuses
            fulfillment_statuses = integration.get_settings_value('receive_order_fulfillment_statuses')
            if 'any' in fulfillment_statuses:
                integration.set_settings_value(
                    'receive_order_fulfillment_statuses',
                    'fulfilled,in_progress,on_hold,partially_fulfilled,request_declined,scheduled,unfulfilled',
                )
            else:
                if 'open' in fulfillment_statuses:
                    fulfillment_statuses = fulfillment_statuses.replace('open', 'unfulfilled')

                if 'pending_fulfillment' in fulfillment_statuses:
                    fulfillment_statuses = fulfillment_statuses.replace('pending_fulfillment', 'in_progress')

                if 'restocked' in fulfillment_statuses:
                    fulfillment_statuses = fulfillment_statuses.replace('restocked', 'unfulfilled')

                integration.set_settings_value('receive_order_fulfillment_statuses', fulfillment_statuses)

            # 1.3 Migrate the receive_order_financial_statuses
            financial_statuses = integration.get_settings_value('receive_order_financial_statuses')
            if 'any' in financial_statuses:
                integration.set_settings_value(
                    'receive_order_financial_statuses',
                    'authorized,expired,paid,partially_paid,partially_refunded,pending,refunded,voided',
                )

    # 2. Update integration.res.lang.external fields for shopify
    records = env['integration.res.lang.external'] \
        .search([('integration_id.type_api', '=', 'shopify')])

    for record in records:
        code = record.code
        record.code = code.split('_')[0]
