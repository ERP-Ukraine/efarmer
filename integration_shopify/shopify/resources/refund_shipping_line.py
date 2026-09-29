# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class RefundShippingLine(GqlDict):
    """A shipping line included in a Shopify refund (full or partial shipping-fee
    refund). Carries the refunded shipping subtotal and tax as MoneyBags; the
    underlying ShippingLine is not needed — the base flow matches the refund to the
    credit note delivery line by the is_delivery flag, not by external id.
    """

    _gid_name = 'RefundShippingLine'

    @property
    def subtotal_amount_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['subtotalAmountSet'] or {}))

    @property
    def tax_amount_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['taxAmountSet'] or {}))
