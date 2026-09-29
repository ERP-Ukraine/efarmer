# See LICENSE file for full copyright and licensing details.

import logging
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .init_integration_shopify import IntegrationShopifyBase
# The adapter under test is the patched client, whose Shop overrides get_access_scopes — patching
# the real resource class would leave that override in place.
from .patch.resources_patch import Shop


SCOPES_WITHOUT_RETURNS = [
    'read_orders',
    'write_orders',
    'read_products',
    'write_products',
]
SCOPES_WITH_RETURNS = SCOPES_WITHOUT_RETURNS + ['read_returns', 'write_returns']


@tagged('post_install', '-at_install', 'test_shopify_returns_scope_guard')
class TestShopifyReturnsScopeGuard(IntegrationShopifyBase):
    """Enabling Returns & Refunds sync is the moment to check the access scopes.

    A store upgrading from an earlier version has not granted read_returns. Telling them while
    they are looking at the setting beats letting it surface later as a failed import job.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration.write({
            'enable_returns_refunds_sync': False,
        })

    def _patch_scopes(self, scopes):
        return patch.object(Shop, 'get_access_scopes', return_value=scopes)

    def test_enabling_is_blocked_when_returns_scopes_missing(self):
        with self._patch_scopes(SCOPES_WITHOUT_RETURNS):
            with self.assertRaises(UserError) as caught:
                self.integration.write({'enable_returns_refunds_sync': True})

        message = str(caught.exception)
        self.assertIn('read_returns', message)
        self.assertIn('write_returns', message)

    def test_enabling_succeeds_when_returns_scopes_granted(self):
        with self._patch_scopes(SCOPES_WITH_RETURNS):
            self.integration.write({'enable_returns_refunds_sync': True})

        self.assertTrue(self.integration.enable_returns_refunds_sync)

    def test_unreachable_store_does_not_block_saving(self):
        """A failed check is not a failed check result. The save goes through and the user is
        told the permissions could not be verified."""
        before = len(self.integration.message_ids)

        # The connection failure is intentional (that's what this test exercises), so
        # assertLogs both captures and mutes the WARNING it would otherwise print, while still
        # failing the test if the code stops logging it at all.
        with self.assertLogs(
            'odoo.addons.integration_shopify.models.sale_integration', logging.WARNING,
        ), patch.object(Shop, 'get_access_scopes', side_effect=OSError('connection refused')):
            self.integration.write({'enable_returns_refunds_sync': True})

        self.assertTrue(
            self.integration.enable_returns_refunds_sync,
            'An unreachable store must not stop the setting from being saved',
        )
        self.assertGreater(
            len(self.integration.message_ids), before,
            'The user must be told the permissions could not be verified',
        )

    def test_disabling_is_never_blocked(self):
        """Turning the feature off needs no permission the store might lack."""
        with self._patch_scopes(SCOPES_WITH_RETURNS):
            self.integration.write({'enable_returns_refunds_sync': True})

        with self._patch_scopes(SCOPES_WITHOUT_RETURNS):
            self.integration.write({'enable_returns_refunds_sync': False})

        self.assertFalse(self.integration.enable_returns_refunds_sync)

    def test_scopes_checked_only_on_the_transition(self):
        """Re-saving an already-enabled integration must not re-run the check, or a store that
        later loses the scope could no longer save anything at all."""
        with self._patch_scopes(SCOPES_WITH_RETURNS):
            self.integration.write({'enable_returns_refunds_sync': True})

        with self._patch_scopes(SCOPES_WITHOUT_RETURNS):
            # Same value again: no transition, so no check and no error.
            self.integration.write({'enable_returns_refunds_sync': True})

        self.assertTrue(self.integration.enable_returns_refunds_sync)

    def test_webhook_topics_exclude_returns_when_disabled(self):
        routes = self.integration._retrieve_webhook_routes()

        self.assertNotIn('returns', routes)
        self.assertNotIn('refunds', routes)
        self.assertIn('orders', routes)

    def test_webhook_topics_include_returns_when_enabled(self):
        with self._patch_scopes(SCOPES_WITH_RETURNS):
            self.integration.write({'enable_returns_refunds_sync': True})

        routes = self.integration._retrieve_webhook_routes()

        self.assertIn('returns', routes)
        self.assertIn('refunds', routes)
        self.assertEqual(len(routes['returns']), 6)

    def test_webhooks_not_registered_when_integration_has_none(self):
        """Toggling must not create webhooks for an integration that deliberately has none."""
        self.integration.webhook_line_ids.unlink()

        with patch.object(
            type(self.integration), 'create_webhooks',
        ) as create_webhooks:
            with self._patch_scopes(SCOPES_WITH_RETURNS):
                self.integration.write({'enable_returns_refunds_sync': True})

        create_webhooks.assert_not_called()
