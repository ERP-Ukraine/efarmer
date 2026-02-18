# See LICENSE file for full copyright and licensing details.

from .base import GqlDict, ReadMixin


class ShopLocale(GqlDict, ReadMixin):

    _gid_name = 'ShopLocale'
    _request_name = 'shopLocale'
    _body = GqlDict._tmpl.SHOP_LOCALE_BODY

    def __repr__(self):
        return f'{self._gid_name}({self.locale}, primary={self.primary}, published={self.published})'

    def __bool__(self):
        return bool(self.locale)

    @property
    def country_code(self):
        self.ensure_one()
        return self.shop_country_code or self.locale.upper()

    def fetch_all(self):

        response = self._env.execute(
            'query { %s { %s } }' % (self._request_name_plural, self.default_body()),
        )

        result = self._extract(response, f'data.{self._request_name_plural}', list)

        return [self._new(**x) for x in result]

    def to_odoo_format(self):
        self.ensure_one()

        return {
            'id': self.locale,
            'name': self.name,
            'code': self.locale,
            'primary': self.primary,
            'external_reference': self.locale,
        }
