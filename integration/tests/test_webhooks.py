# See LICENSE file for full copyright and licensing details.

from unittest.mock import Mock, PropertyMock, patch

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_webhooks')
class TestIntegrationWebhooks(OdooIntegrationInit):

    def setUp(self):
        super(TestIntegrationWebhooks, self).setUp()

        self.webhook_1, self.webhook_2 = self.env['integration.webhook.line'].create([
            {
                'name': 'Order Created',
                'technical_name': 'orders/create',
                'external_ref': '101',
                'integration_id': self.integration_no_api_1.id,
            },
            {
                'name': 'Order Updated',
                'technical_name': 'orders/updated',
                'external_ref': '102',
                'integration_id': self.integration_no_api_1.id,
            },
        ])

    def test_delete_single_webhook(self):
        adapter = Mock()

        with patch.object(
            type(self.integration_no_api_1),
            'adapter',
            new_callable=PropertyMock,
            return_value=adapter,
        ):
            self.webhook_1.action_delete_webhook()

        adapter.unlink_existing_webhooks.assert_called_once_with(['101'])
        self.assertFalse(self.webhook_1.exists())
        self.assertTrue(self.webhook_2.exists())
