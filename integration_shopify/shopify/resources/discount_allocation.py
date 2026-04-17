# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DiscountAllocation(GqlDict):

    _gid_name = 'DiscountAllocation'
    _body = GqlDict._tmpl.DISCOUNT_ALLOCATION_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def discount_application(self):
        """
        Return the human-readable identifier of the discount application:
          - coupon code for DiscountCodeApplication
          - title for automatic / manual / script discounts
          - empty string when the field is absent (old API responses)
        """
        self.ensure_one()
        application = self['discountApplication'] or {}
        return application.get('code') or application.get('title') or ''

    @property
    def amount_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['allocatedAmountSet'] or {}))
