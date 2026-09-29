# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class ReturnsRefundsAccountingTestBase(TransactionCase):
    """Shared base for returns/refunds tests that exercise the accounting
    flow (credit notes, refund payments, return pickings against done
    deliveries).

    Why not `OdooIntegrationInit`: that base uses `test_integration_company_1`
    from `init_sale_integration.xml`, which has no chart of accounts
    installed. Refund/payment flows need a full CoA (sale taxes, bank
    journals with outstanding accounts, receivables), so accounting tests
    sit on `base.main_company` and its demo CoA instead.

    The class env is pre-loaded with `queue_job__no_delay=1` so any
    dispatch job enqueued via lifecycle hooks runs synchronously in test
    context without per-call `with_context(...)`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Several tests deliberately trigger a hard-fail guard (e.g. E514, E516), which
        # external_order_resource.py logs via _log_processing_failed() on every record
        # failure. Muted for the whole class so expected, per-test failure logging doesn't
        # clutter run output.
        resource_logger = mute_logger(
            'odoo.addons.integration.models.external.external_order_resource',
        )
        resource_logger.__enter__()
        cls.addClassCleanup(resource_logger.__exit__)

        # Run all enqueued jobs synchronously for the entire test class
        cls.env = cls.env(context=dict(cls.env.context, queue_job__no_delay=1))

        cls.company = cls.env.ref('base.main_company')

        cls.bank_journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.bank_journal:
            # Derive a per-class code so two classes inheriting from this base
            # never collide on `unique_code_company_id` should both ever hit
            # the create-fallback branch in the same DB.
            cls.bank_journal = cls.env['account.journal'].create({
                'name': 'Test Returns/Refunds Bank',
                'type': 'bank',
                'code': ('TRR%s' % cls.__name__)[:5],
                'company_id': cls.company.id,
            })

        cls.tax = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.company.id),
            ('amount_type', '=', 'percent'),
        ], limit=1)

        cls.partner = cls.env['res.partner'].create(
            {'name': 'Returns/Refunds Test Customer'},
        )

    @classmethod
    def _create_test_integration(cls, name, **extra):
        """Create a no_api integration with returns/refunds sync enabled."""
        vals = {
            'name': name,
            'type_api': 'no_api',
            'company_id': cls.company.id,
            'enable_returns_refunds_sync': True,
        }
        vals.update(extra)
        return cls.env['sale.integration'].create(vals)
