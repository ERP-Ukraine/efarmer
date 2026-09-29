# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class MoneyBag(GqlDict):

    _gid_name = 'MoneyBag'
    _body = GqlDict._tmpl.MONEY_BAG_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    def _money(self, use_customer_currency: bool = False):
        """Return the nested MoneyV2 (presentment or shop)."""
        self.ensure_one()
        raw = self.presentmentMoney if use_customer_currency else self.shopMoney

        return self._env.MoneyV2.set(**(raw or {}))

    def get_amount(self, use_customer_currency: bool = False) -> float:
        return self._money(use_customer_currency).amount

    def get_currency(self, use_customer_currency: bool = False) -> str:
        return self._money(use_customer_currency).currency_code or ''
