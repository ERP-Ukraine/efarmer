# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestExternalIntegrationWizard(OdooIntegrationInit):
    """Tests for the "Manage Store Connections" wizard.

    - "Link only" / "Unlink" change membership and never push.
    - "Link & export now" requires an explicit confirmation, then links AND pushes.
    """

    def _make_wizard(self, records, line_actions):
        # line_actions: list of (integration, action) tuples.
        lines = [
            (0, 0, {'integration_id': integration.id, 'integration_action': action})
            for integration, action in line_actions
        ]
        return self.env['external.integration.wizard'].with_context(
            active_ids=records.ids,
            active_model=records._name,
        ).create({'integration_line_ids': lines})

    def test_link_only_does_not_push(self):
        integration = self.integration_no_api_2  # variant is not linked to it yet
        variant = self.product_pp_1
        self.assertNotIn(integration, variant.integration_ids)

        wizard = self._make_wizard(variant, [(integration, 'link')])
        result = wizard.apply_integration()

        # Linked, but nothing was pushed.
        self.assertIn(integration, variant.integration_ids)
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')
        for force in (True, False):
            key = self.get_integration_identity_key(
                integration, variant.product_tmpl_id, export_images=integration.allow_export_images, force=force,
            )
            self.assertFalse(self.get_queue_job(key))

    def test_unlink_does_not_push(self):
        integration = self.integration_no_api_1  # variant is linked to it
        variant = self.product_pp_1
        self.assertIn(integration, variant.integration_ids)

        wizard = self._make_wizard(variant, [(integration, 'unlink')])
        result = wizard.apply_integration()

        self.assertNotIn(integration, variant.integration_ids)
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

    def test_link_export_requires_confirmation_then_pushes(self):
        integration = self.integration_no_api_2
        variant = self.product_pp_1
        self.assertNotIn(integration, variant.integration_ids)

        wizard = self._make_wizard(variant, [(integration, 'link_export')])

        # 1. First apply -> confirmation step; nothing is linked or pushed yet.
        action = wizard.apply_integration()
        self.assertEqual(wizard.state, 'confirm')
        self.assertEqual(action.get('res_model'), 'external.integration.wizard')
        self.assertNotIn(integration, variant.integration_ids)

        # 2. Confirm -> link AND push.
        result = wizard.apply_integration()
        self.assertIn(integration, variant.integration_ids)
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

        key = self.get_integration_identity_key(
            integration, variant.product_tmpl_id, export_images=integration.allow_export_images, force=True,
        )
        self.assertTrue(self.get_queue_job(key))

    def test_back_returns_to_draft(self):
        integration = self.integration_no_api_2
        variant = self.product_pp_1

        wizard = self._make_wizard(variant, [(integration, 'link_export')])
        wizard.apply_integration()
        self.assertEqual(wizard.state, 'confirm')

        action = wizard.action_back()
        self.assertEqual(wizard.state, 'draft')
        self.assertEqual(action.get('res_model'), 'external.integration.wizard')
        # Still nothing applied.
        self.assertNotIn(integration, variant.integration_ids)
