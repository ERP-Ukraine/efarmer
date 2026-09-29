# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class MoneyV2(GqlDict):
    """Shopify MoneyV2 — amount + currencyCode.

    https://shopify.dev/docs/api/admin-graphql/2026-04/objects/MoneyV2
    """

    _gid_name = 'MoneyV2'
    _body = GqlDict._tmpl.MONEY_V2_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def amount(self) -> float:
        """Decimal amount as float (Shopify may send "519.3", "0.0")."""
        self.ensure_one()
        raw = self['amount']
        if raw is None or raw is False or raw == '':
            return 0.0

        return float(raw)

    @property
    def currency_code(self) -> str | bool:
        """ISO currency code, or False when missing."""
        self.ensure_one()

        return self['currencyCode'] or False
