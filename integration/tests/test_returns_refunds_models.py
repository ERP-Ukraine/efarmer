# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .config.integration_init import load_xml


@tagged('post_install', '-at_install', 'test_returns_refunds_models')
class TestReturnsRefundsModels(TransactionCase):
    """Tests for returns/refunds model infrastructure: field defaults,
    computed fields, settings constraints, and feature-flag gating."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        cls.integration = cls.env.ref('integration.integration_no_api_1')
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.order = cls.env['sale.order'].with_context(
            queue_job__no_delay=1,
        ).create({
            'partner_id': cls.partner.id,
            'integration_id': cls.integration.id,
        })

    # --- integration_id resolution via erp_order_id ---

    def test_integration_id_resolves_from_erp_order(self):
        """Both return and refund models resolve integration_id via the
        related field on erp_order_id (no direct integration_id field on
        the records themselves).
        """
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/111',
            'erp_order_id': self.order.id,
        })
        self.assertTrue(ret.id, 'Return record should persist')
        self.assertEqual(ret.state, 'open', 'Default state should be open')
        self.assertEqual(
            ret.integration_id, self.integration,
            'Return: integration_id should resolve from erp_order_id',
        )

        refund = self.env['external.order.refund'].create({
            'external_str_id': 'gid://shopify/Refund/333',
            'erp_order_id': self.order.id,
        })
        self.assertTrue(refund.id, 'Refund record should persist')
        self.assertEqual(
            refund.integration_id, self.integration,
            'Refund: integration_id should resolve from erp_order_id',
        )

    # --- Computed fields ---

    def test_is_placeholder_computed_from_amount_and_linked_return(self):
        """is_placeholder is True only when amount=0 AND a linked return
        exists. _process() short-circuits to mark_skipped on placeholder
        refunds; this compute drives that branch.
        """
        ret = self.env['external.order.return'].create({
            'external_str_id': 'gid://shopify/Return/500',
            'erp_order_id': self.order.id,
        })
        # Placeholder: amount=0, linked return exists
        refund_placeholder = self.env['external.order.refund'].create({
            'external_str_id': 'gid://shopify/Refund/501',
            'erp_order_id': self.order.id,
            'total_refunded_amount': 0,
            'linked_return_id': ret.id,
        })
        self.assertTrue(
            refund_placeholder.is_placeholder,
            'Refund with amount=0 and linked return should be a placeholder',
        )

        # Real refund: amount > 0
        refund_real = self.env['external.order.refund'].create({
            'external_str_id': 'gid://shopify/Refund/502',
            'erp_order_id': self.order.id,
            'total_refunded_amount': 10.0,
        })
        self.assertFalse(
            refund_real.is_placeholder,
            'Refund with amount > 0 should not be a placeholder',
        )

        # Anomalous: amount=0, no linked return — _process() raises here.
        refund_anomalous = self.env['external.order.refund'].create({
            'external_str_id': 'gid://shopify/Refund/503',
            'erp_order_id': self.order.id,
            'total_refunded_amount': 0,
        })
        self.assertFalse(
            refund_anomalous.is_placeholder,
            'Refund with amount=0 and no linked return should not be a placeholder',
        )

    # --- Feature flag on _raise_if_refund_found ---

    def test_refund_transaction_allowed_when_sync_enabled(self):
        """When enable_returns_refunds_sync=True, the legacy
        _raise_if_refund_found() guard is disabled so refund transactions
        can be processed by the new refund flow."""
        self.integration.write({
            'enable_returns_refunds_sync': True,
        })
        transaction = self.env['external.order.transaction'].create({
            'name': 'TX-REFUND-1',
            'erp_order_id': self.order.id,
            'external_str_id': 'ext-tx-1',
            'external_status': 'success',
            'kind': 'refund',
            'amount': '10.00',
            'currency': 'USD',
        })
        # Should NOT raise when feature flag is on
        transaction._raise_if_refund_found()

    def test_refund_transaction_blocked_when_sync_disabled(self):
        """When enable_returns_refunds_sync=False, the legacy
        _raise_if_refund_found() guard is active and rejects refund
        transactions to preserve backward compatibility."""
        self.integration.write({
            'enable_returns_refunds_sync': False,
        })
        transaction = self.env['external.order.transaction'].create({
            'name': 'TX-REFUND-2',
            'erp_order_id': self.order.id,
            'external_str_id': 'ext-tx-2',
            'external_status': 'success',
            'kind': 'refund',
            'amount': '10.00',
            'currency': 'USD',
        })
        with self.assertRaises(ValidationError):
            transaction._raise_if_refund_found()
