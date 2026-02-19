# See LICENSE file for full copyright and licensing details.

from .base import GqlDict, CreateMixin, UpdateMixin


class PriceListPrice(GqlDict, CreateMixin, UpdateMixin):

    _gid_name = 'PriceListPrice'
    _body = GqlDict._tmpl.PRICE_LIST_PRICE_BODY

    def __repr__(self):
        if self:
            return f'{self._gid_name}({self.variant.id}, ' \
                f'price={self.price_fmt}, compare_at_price={self.compare_at_price_fmt}) ' \
                f'/ {self.origin_type})'

        return super().__repr__()

    def __bool__(self):
        return bool(self['variant'])

    @property
    def variant(self):
        self.ensure_one()
        return self._env.ProductVariant.set(**self['variant'])

    @property
    def origin_type(self):
        self.ensure_one()
        return self.originType

    @property
    def price(self):
        self.ensure_one()
        return self['price']['amount']

    @property
    def price_currency(self):
        self.ensure_one()
        return self['price']['currencyCode']

    @property
    def price_fmt(self):
        return f'{self.price} {self.price_currency}'

    @property
    def compare_at_price(self):
        self.ensure_one()
        compare_at_price = self['compareAtPrice']
        if compare_at_price:
            return compare_at_price['amount']
        return None

    @property
    def compare_at_price_currency(self):
        self.ensure_one()
        compare_at_price = self['compareAtPrice']
        if compare_at_price:
            return compare_at_price['currencyCode']
        return None

    @property
    def compare_at_price_fmt(self):
        return f'{self.compare_at_price} {self.compare_at_price_currency}'
