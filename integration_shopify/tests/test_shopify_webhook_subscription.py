# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch as mock_patch

from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase
from ..shopify.exceptions import ShopifyApiError
from ..shopify.resources.webhook_subscription import WebhookSubscription


@tagged('post_install', '-at_install', 'test_shopify_webhook_subscription')
class TestShopifyWebhookSubscription(IntegrationShopifyBase):
    """WebhookSubscription.create()'s reclaim-on-conflict retry: a previous run can leave a
    subscription registered on Shopify without Odoo ever recording it (e.g. it was created
    here but a later topic in the same batch failed before any webhook_line was saved)."""

    def test_create_reclaims_existing_subscription_on_conflict(self):
        """On 'has already been taken', the existing subscription is deleted and
        creation is retried once — succeeding the second time."""
        calls = {'create': 0, 'delete_existing': 0}

        def _fake_create(*_args, **_kwargs):
            calls['create'] += 1
            if calls['create'] == 1:
                raise ShopifyApiError('Address for this topic has already been taken')
            return 'created'

        def _fake_delete_existing(*_args, **_kwargs):
            calls['delete_existing'] += 1

        with mock_patch.object(WebhookSubscription, '_create', _fake_create), \
                mock_patch.object(WebhookSubscription, '_delete_existing', _fake_delete_existing):
            result = self.integration.adapter.gql.WebhookSubscription.create(
                'ORDERS_REFUNDED', 'https://example.com/hook',
            )

        self.assertEqual(result, 'created')
        self.assertEqual(calls['create'], 2, 'Creation must be retried exactly once after reclaiming.')
        self.assertEqual(calls['delete_existing'], 1)

    def test_create_does_not_reclaim_on_unrelated_error(self):
        """A ShopifyApiError unrelated to a taken address propagates as-is —
        no reclaim, no retry."""
        def _fake_create(*_args, **_kwargs):
            raise ShopifyApiError('Some other Shopify error')

        with mock_patch.object(WebhookSubscription, '_create', _fake_create):
            with self.assertRaises(ShopifyApiError):
                self.integration.adapter.gql.WebhookSubscription.create(
                    'ORDERS_REFUNDED', 'https://example.com/hook',
                )
