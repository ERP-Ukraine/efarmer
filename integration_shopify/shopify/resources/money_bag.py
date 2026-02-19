# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class MoneyBag(GqlDict):

    _gid_name = 'MoneyBag'
    _body = GqlDict._tmpl.MONEY_BAG_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    def get_amount(self, use_customer_currency: bool = False) -> float:
        self.ensure_one()

        if use_customer_currency:
            return float(self.presentmentMoney and self.presentmentMoney['amount'] or 0)

        return float(self.shopMoney and self.shopMoney['amount'] or 0)

    def get_currency(self, use_customer_currency: bool = False) -> str:
        self.ensure_one()

        if use_customer_currency:
            return self.presentmentMoney and self.presentmentMoney['currencyCode'] or ''

        return self.shopMoney and self.shopMoney['currencyCode'] or ''
