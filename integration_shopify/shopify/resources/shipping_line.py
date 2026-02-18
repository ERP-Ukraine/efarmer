# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class ShippingLine(GqlDict):

    _gid_name = 'ShippingLine'
    _body = GqlDict._tmpl.SHIPPING_LINE_BODY

    @property
    def current_discounted_price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['currentDiscountedPriceSet'] or {}))

    @property
    def tax_lines(self):
        self.ensure_one()
        return [self._env.TaxLine.set(**x) for x in (self['taxLines'] or [])]

    def get_price(self, use_customer_currency: bool) -> float:
        self.ensure_one()
        money_bag = self.current_discounted_price_set
        return money_bag.get_amount(use_customer_currency)
