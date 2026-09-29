# See LICENSE file for full copyright and licensing details.

import logging
from datetime import date, datetime

from .shopify_payments_base import ShopifyPaymentsNested


_logger = logging.getLogger(__name__)

# Summary MoneyV2 members → Odoo field names (snake_case with summary_ prefix).
_SUMMARY_FIELD_MAP = (
    ('chargesGross', 'summary_charges_gross'),
    ('chargesFee', 'summary_charges_fee'),
    ('refundsFeeGross', 'summary_refunds_fee_gross'),
    ('refundsFee', 'summary_refunds_fee'),
    ('adjustmentsGross', 'summary_adjustments_gross'),
    ('adjustmentsFee', 'summary_adjustments_fee'),
    ('reservedFundsGross', 'summary_reserved_funds_gross'),
    ('reservedFundsFee', 'summary_reserved_funds_fee'),
    ('retriedPayoutsGross', 'summary_retried_payouts_gross'),
    ('retriedPayoutsFee', 'summary_retried_payouts_fee'),
    ('advanceGross', 'summary_advance_gross'),
    ('advanceFees', 'summary_advance_fees'),
    ('usdcRebateCreditAmount', 'summary_usdc_rebate_credit_amount'),
)


class ShopifyPaymentsPayout(ShopifyPaymentsNested):
    """ShopifyPaymentsPayout — nested under shopifyPaymentsAccount.payouts."""

    _gid_name = 'ShopifyPaymentsPayout'
    _request_name = 'payout'
    _body = ShopifyPaymentsNested._tmpl.SHOPIFY_PAYMENTS_PAYOUT_BODY

    @property
    def net(self):
        self.ensure_one()
        return self._env.MoneyV2.set(**(self['net'] or {}))

    @property
    def summary(self) -> dict:
        self.ensure_one()
        return self['summary'] or {}

    @property
    def issued_at(self) -> str:
        self.ensure_one()
        return self['issuedAt'] or ''

    @property
    def status(self) -> str:
        self.ensure_one()
        return self['status'] or ''

    @property
    def transaction_type(self) -> str:
        self.ensure_one()
        return self['transactionType'] or ''

    @property
    def legacy_resource_id(self):
        self.ensure_one()
        return self['legacyResourceId']

    @property
    def external_trace_id(self) -> str | bool:
        self.ensure_one()
        return self['externalTraceId'] or False

    def fetch_payouts(
        self,
        date_from: date | datetime | str | None = None,
    ) -> list:
        """Paginate all payouts with issued_at >= date_from (exhausted in-job).

        :param date_from: date/datetime/str used in `issued_at:>=YYYY-MM-DD`, or None for all.
        :return: list of ShopifyPaymentsPayout instances
        """
        filter_params = None
        if date_from is not None:
            if isinstance(date_from, datetime):
                date_str = date_from.strftime('%Y-%m-%d')
            elif isinstance(date_from, date):
                date_str = date_from.isoformat()
            else:
                date_str = str(date_from)[:10]
            # No space after the colon — Shopify search splits on whitespace.
            filter_params = f'issued_at:>={date_str}'

        self.reset_context()
        return self.get_batch(filter_params=filter_params, limit=self._infinity)

    def to_odoo_format(self) -> dict:
        """Convert to a dict matching external.payout field names (currency as ISO code).

        Pure field mapping — never raises. Currency policy (missing code, summary
        member mismatch) is enforced on ``external.payout._create_or_update_from_external``
        so one poison payout cannot abort a batch ``get_payouts`` / discovery run.
        """
        self.ensure_one()
        net = self.net
        currency_code = net.currency_code

        summary = self.summary
        summary_vals = {}
        currency_issues = []
        if not currency_code:
            currency_issues.append(
                f'Payout {self.id} has no net.currencyCode — cannot import without a currency'
            )

        for gql_key, field_name in _SUMMARY_FIELD_MAP:
            member = self._env.MoneyV2.set(**(summary.get(gql_key) or {}))
            amount = member.amount
            member_currency = member.currency_code
            # Record consistency for every non-zero summary member; import refuses mismatch.
            if (
                currency_code
                and amount
                and member_currency
                and member_currency != currency_code
            ):
                currency_issues.append(
                    f'Payout {self.id} summary.{gql_key} currency {member_currency} '
                    f'differs from net currency {currency_code} — cross-currency payouts '
                    f'are not supported in v1'
                )
            summary_vals[field_name] = amount

        issued_at = self.issued_at
        issued_date = issued_at[:10] if issued_at else False

        status_raw = self.status.lower() or False
        txn_type_raw = self.transaction_type.lower() or False

        # legacyResourceId is UnsignedInt64 serialised as a decimal string.
        legacy_id = self.legacy_resource_id
        if legacy_id is None or legacy_id is False:
            legacy_id = self.id_str
        else:
            legacy_id = str(legacy_id)

        return {
            'external_str_id': legacy_id,
            'name': f'Payout #{legacy_id}',
            'issued_date': issued_date,
            'status': status_raw,
            'payout_transaction_type': txn_type_raw,
            'currency_code': currency_code,
            'amount_net': net.amount,
            'external_trace_id': self.external_trace_id,
            # Adapter-only: popped by _create_or_update_from_external, never stored.
            '_currency_issues': currency_issues,
            **summary_vals,
        }
