# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum, GqlDict


class PriceListAdjustmentType(GQLEnum):

    percentage_decrease = 'PERCENTAGE_DECREASE'
    percentage_increase = 'PERCENTAGE_INCREASE'

    @property
    def is_increase(self):
        return self == self.percentage_increase

    @property
    def is_decrease(self):
        return self == self.percentage_decrease


class PriceListCompareAtMode(GQLEnum):

    adjusted = 'ADJUSTED'  # The compare at price is adjusted based on percentage specified in price list.
    nullify = 'NULLIFY'  # The compare at prices are set to null unless explicitly defined by a fixed price value.

    @property
    def is_adjusted(self):
        return self == self.adjusted

    @property
    def is_nullified(self):
        return self == self.nullify


class PriceListAdjustment(GqlDict):

    _gid_name = 'PriceListAdjustment'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def type_code(self):
        self.ensure_one()
        return self['type']

    @property
    def type_enum(self):
        return PriceListAdjustmentType(self.type_code)

    @property
    def value(self):
        self.ensure_one()
        return self['value']

    @property
    def is_increase(self):
        return self.type_enum.is_increase

    @property
    def is_decrease(self):
        return self.type_enum.is_decrease


class PriceListAdjustmentSettings(GqlDict):

    _gid_name = 'PriceListAdjustmentSettings'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def compare_at_mode(self):
        self.ensure_one()
        return PriceListCompareAtMode(self['compareAtMode'])


class PriceListParent(GqlDict):

    _gid_name = 'PriceListParent'
    _body = GqlDict._tmpl.PRICELIST_PARENT_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def adjustment(self):
        self.ensure_one()
        return PriceListAdjustment.set(**self['adjustment'])

    @property
    def settings(self):
        self.ensure_one()
        return PriceListAdjustmentSettings.set(**self['settings'])
