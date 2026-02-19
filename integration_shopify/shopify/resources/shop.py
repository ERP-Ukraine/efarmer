# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class Shop(ShopifyResourceRead):

    _gid_name = 'Shop'
    _request_name = 'shop'
    _body = ShopifyResourceRead._tmpl.SHOP_BODY

    def init(self):
        self.get_current()
        self.get_access_scopes()
        return self

    @property
    def billing_address(self):
        self.ensure_one()
        return self._env.MailingAddress.set(**(self['billingAddress'] or {}))

    @property
    def country_code(self):
        self.ensure_one()
        return self.billing_address.country_code

    @property
    def currency_code(self):
        self.ensure_one()
        return self.currencyCode

    @property
    def locales(self):
        self.ensure_one()

        if not self.key_exist('locales'):
            self.get_locales()

        return [self._env.ShopLocale.set(**x) for x in self['locales']]

    @property
    def weight_unit(self):
        self.ensure_one()
        return self._env.WeightUnit.convert_weight_unit_in(self.weightUnit)

    @property
    def product_tags(self):
        self.ensure_one()
        return self.productTags

    @property
    def access_scopes(self):
        self.ensure_one()

        if not self.key_exist('accessScopes'):
            self.get_access_scopes()

        return self.accessScopes

    def get_access_scopes(self):
        self.ensure_one()

        response = self.execute(
            'query { currentAppInstallation { accessScopes { handle } } }',
        )

        result = self._extract(response, 'data.currentAppInstallation.accessScopes', list)
        self.set(accessScopes=[x['handle'] for x in result])

        return self['accessScopes']

    def get_primary_locale(self):
        self.ensure_one()

        if not self.key_exist('locales'):
            self.get_locales()

        for x in self.locales:
            if x.primary:
                return x

        raise ValueError('No primary locale found')

    def get_current(self):
        response = self.execute('query { %s { %s } }' % (self._request_name, self.default_body()))

        result = self._extract_response(response)
        self.set(**(result or {}))

        return self

    def get_locales(self):
        self.ensure_one()

        locales = self._env.ShopLocale.fetch_all()

        self.set(
            locales=[{**x.to_dict(), 'shop_country_code': self.country_code} for x in locales],
        )

        return locales
