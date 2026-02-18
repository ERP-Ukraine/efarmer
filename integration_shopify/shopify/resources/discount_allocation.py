# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DiscountAllocation(GqlDict):

    _gid_name = 'DiscountAllocation'
    _body = GqlDict._tmpl.DISCOUNT_ALLOCATION_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def discount_application(self):  # TODO: implement it (allocationMethod + targetSelection + targetType)
        raise NotImplementedError('The discountApplication is not implemented')

    @property
    def amount_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['allocatedAmountSet'] or {}))
