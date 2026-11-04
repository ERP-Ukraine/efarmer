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

        cls.company = cls.env.ref('base.main_company')

        # Pin the class env for the whole test class:
        # - queue_job__no_delay runs enqueued jobs synchronously in test context.
        # - allowed_company_ids lists every company with `cls.company` FIRST. The first entry makes
        #   `env.company` resolve to `cls.company`, so company-dependent reads (notably
        #   `product.taxes_id`) return this company's values. Listing all companies makes
        #   `env.companies` span the whole DB, so `product.template.create` finds no "other"
        #   companies and skips `_force_default_tax` (account/models/product.py). Otherwise, on a
        #   multi-company DB, every other company's default sale tax is force-added to the
        #   company-shared products created here, lands on a `cls.company` order line and trips
        #   `_check_company` with a company-crossover error.
        other_company_ids = cls.env['res.company'].sudo().search([('id', '!=', cls.company.id)]).ids
        cls.env = cls.env(context=dict(
            cls.env.context,
            queue_job__no_delay=1,
            allowed_company_ids=cls.company.ids + other_company_ids,
        ))
        cls.company = cls.company.with_env(cls.env)

        # Always a dedicated journal: reusing an existing one ties the tests to the DB's own
        # setup. With Enterprise `accountant` installed, a payment method line without an
        # outstanding account registers payments without a journal entry (Community forces a
        # fallback account instead), leaving the invoice 'in_payment' with its full residual,
        # so every refund would soft-fail with E514. The journal code is left to Odoo's
        # compute so it never collides with an existing one.
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Test Returns/Refunds Bank',
            'type': 'bank',
            'company_id': cls.company.id,
        })
        Account = cls.env['account.account'].with_company(cls.company)
        outstanding_account = Account.create({
            'name': 'Test Returns/Refunds Outstanding',
            'code': Account._search_new_account_code('999900'),
            'account_type': 'asset_current',
            'reconcile': True,
        })
        (
            cls.bank_journal.inbound_payment_method_line_ids
            | cls.bank_journal.outbound_payment_method_line_ids
        ).payment_account_id = outstanding_account

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
