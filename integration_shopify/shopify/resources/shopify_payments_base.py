# See LICENSE file for full copyright and licensing details.

from datetime import datetime, timezone

from odoo import _

from .base import ShopifyResourceRead
from ..exceptions import ShopifyApiError


def parse_utc_datetime(value: str | datetime | None) -> datetime | bool:
    """Convert a Shopify ISO-8601 timestamp to a naive UTC datetime, or False.

    Shopify returns `2026-07-29T01:21:08Z`, which Odoo's Datetime field cannot coerce from a
    string — it expects `%Y-%m-%d %H:%M:%S` — so the conversion has to happen here. Odoo
    stores Datetime naive in UTC, hence dropping tzinfo after normalising the offset.
    """
    if not value:
        return False
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            return False
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class ShopifyPaymentsNested(ShopifyResourceRead):
    """Base for connections nested under the `shopifyPaymentsAccount` singleton.

    `payouts` and `balanceTransactions` are not root query fields, so the generic
    `ReadMixin` batch template does not apply — the query wraps them in the account
    object and the cursor is read from there.
    """

    def _use_batch_template(self, values: str, body: str) -> str:
        # Nested under the singleton account — a root `payouts(...)` field does not exist.
        query_ = (
            '{ shopifyPaymentsAccount { %s(%s) { '
            'pageInfo { endCursor hasNextPage } edges { node { %s } } } } }'
        )
        return query_ % (self._request_name_plural, values, body)

    def _base_extract(
        self,
        data: dict,
        key: str | None = None,
        cursor_key: str = 'pageInfo',
    ) -> dict:
        # get_by_ids goes through the root `nodes(ids:)` query, which is not nested under the
        # account — only the connection reads are. Without this, re-reading a payout by id
        # would look for `nodes` inside shopifyPaymentsAccount and always come back empty.
        if key == 'nodes':
            return super()._base_extract(data, key=key, cursor_key=cursor_key)

        key_ = key or self._request_name_plural
        account = self._extract(data, 'data.shopifyPaymentsAccount', dict)
        # A null account is never "no payouts today": the store is not on Shopify Payments,
        # the token lost the payout scopes, or one unavailable field nulled the whole object
        # (verified live with payoutSchedule). Falling back to {} would report an empty
        # window and let the watermark advance over data we never read.
        if not account:
            raise ShopifyApiError(_(
                'Shopify returned no "shopifyPaymentsAccount" object. Either this store does '
                'not use Shopify Payments, or the access token is missing the '
                '"read_shopify_payments_accounts" / "read_shopify_payments_payouts" scopes. '
                'Re-authorize the store to grant payout read access.'
            ))

        data_ = account.get(key_) or {}

        if isinstance(data_, dict):
            self._save_cursor(data_, cursor_key=cursor_key)
        else:
            self.reset_context()

        return data_ if isinstance(data_, dict) else {}
