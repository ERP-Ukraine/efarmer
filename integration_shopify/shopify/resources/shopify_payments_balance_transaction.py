# See LICENSE file for full copyright and licensing details.

import logging

from .shopify_payments_base import (
    ShopifyPaymentsNested,
    parse_utc_datetime,
)


_logger = logging.getLogger(__name__)


class ShopifyPaymentsBalanceTransaction(ShopifyPaymentsNested):
    """ShopifyPaymentsBalanceTransaction — nested under shopifyPaymentsAccount."""

    _gid_name = 'ShopifyPaymentsBalanceTransaction'
    _request_name = 'balanceTransaction'
    _body = ShopifyPaymentsNested._tmpl.SHOPIFY_PAYMENTS_BALANCE_TRANSACTION_BODY

    @property
    def amount(self):
        self.ensure_one()
        return self._env.MoneyV2.set(**(self['amount'] or {}))

    @property
    def fee(self):
        self.ensure_one()
        return self._env.MoneyV2.set(**(self['fee'] or {}))

    @property
    def net(self):
        self.ensure_one()
        return self._env.MoneyV2.set(**(self['net'] or {}))

    @property
    def transaction_type(self):
        self.ensure_one()
        return self._env.ShopifyPaymentsTransactionType(self['type'])

    @property
    def source_type(self):
        self.ensure_one()
        raw = self['sourceType']
        if not raw:
            return False
        return self._env.ShopifyPaymentsSourceType(raw)

    @property
    def test(self) -> bool:
        self.ensure_one()
        return bool(self['test'])

    @property
    def associated_order(self) -> dict:
        self.ensure_one()
        return self['associatedOrder'] or {}

    @property
    def associated_payout(self) -> dict:
        self.ensure_one()
        return self['associatedPayout'] or {}

    @property
    def source_order_transaction_id(self):
        self.ensure_one()
        return self['sourceOrderTransactionId']

    @property
    def source_id(self):
        self.ensure_one()
        return self['sourceId']

    @property
    def adjustment_reason(self) -> str | bool:
        self.ensure_one()
        return self['adjustmentReason'] or False

    @property
    def transaction_date(self):
        self.ensure_one()
        return self['transactionDate']

    def fetch_by_payout(self, payout_legacy_id: int | str) -> list:
        """Fetch all balance transactions for one payout via payments_transfer_id filter.

        :param payout_legacy_id: payout legacyResourceId (int or str). No space after colon.
        :return: list of ShopifyPaymentsBalanceTransaction instances belonging to that payout
        """
        payout_id = str(payout_legacy_id)
        # Dict form is safe — ReadMixin formats as f'{k}:{v}' with no space.
        self.reset_context()
        rows = self.get_batch(
            filter_params={'payments_transfer_id': payout_id},
            limit=self._infinity,
        )

        # Defensive cross-check: associatedPayout.id must resolve to this payout.
        expected = int(payout_id)
        matched = []
        for row in rows:
            associated = row.associated_payout
            associated_id = associated.get('id')
            if not associated_id:
                _logger.warning(
                    'Skipping balance transaction %s: associatedPayout.id is null '
                    '(open-balance row, not part of a payout)',
                    row.id_str,
                )
                continue
            if row.parse_int(associated_id) != expected:
                _logger.warning(
                    'Skipping balance transaction %s: associatedPayout.id %s does not '
                    'match payout %s',
                    row.id_str,
                    associated_id,
                    payout_id,
                )
                continue
            matched.append(row)
        return matched

    def to_odoo_format(self) -> dict:
        """Convert to a dict matching external.payout.line field names.

        Pure field mapping: `reconcile_status` / `reconcile_note` are accounting policy and
        are derived on external.payout.line, not here.
        """
        self.ensure_one()
        amount = self.amount
        fee = self.fee
        net = self.net
        currency_code = (
            amount.currency_code
            or net.currency_code
            or fee.currency_code
        )

        txn_type = self.transaction_type.to_odoo_format()
        source_type = self.source_type.to_odoo_format() if self.source_type else False

        associated_order = self.associated_order
        order_gid = associated_order.get('id') or ''
        external_order_str_id = str(self.parse_int(order_gid)) if order_gid else False
        external_order_name = associated_order.get('name') or False

        # sourceOrderTransactionId is BigInt → plain numeric string, use unparsed.
        source_order_txn = self.source_order_transaction_id
        if source_order_txn is None or source_order_txn is False:
            source_order_txn_str = False
        else:
            source_order_txn_str = str(source_order_txn)

        source_id = self.source_id
        source_str_id = str(source_id) if source_id is not None and source_id is not False else False

        return {
            'external_str_id': self.id_str,
            'transaction_type': txn_type,
            'source_type': source_type,
            'adjustment_reason': self.adjustment_reason,
            'source_str_id': source_str_id,
            'source_order_transaction_str_id': source_order_txn_str,
            'external_order_str_id': external_order_str_id,
            'external_order_name': external_order_name,
            'currency_code': currency_code,
            'amount_gross': amount.amount,
            'amount_fee': fee.amount,
            'amount_net': net.amount,
            'transaction_date': parse_utc_datetime(self.transaction_date),
            'is_test': self.test,
        }
