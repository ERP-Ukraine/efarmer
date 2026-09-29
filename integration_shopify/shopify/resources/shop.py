# See LICENSE file for full copyright and licensing details.

from ..exceptions import ShopifyApiError
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
    def shop_address(self):
        self.ensure_one()
        return self._env.ShopAddress.set(**(self['shopAddress'] or {}))

    @property
    def country_code(self):
        self.ensure_one()
        return self.shop_address.country_code

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

        if not self.key_exist('productTags'):
            self.get_product_tags()

        return self.productTags or []

    @property
    def market_driven_shipping(self):
        """Whether market-driven shipping is enabled on this shop.

        Queried separately from the rest of the shop body: `ShopFeatures.marketDrivenShipping`
        is only present in the schema for shops opted into the (pre-GA, broad rollout
        2026-10-01) feature preview, and Shopify raises "doesn't exist on type" for every
        other shop -- fetching it eagerly in `get_current()` would break shop init, and
        with it every single API call, on any non-preview shop.
        """
        self.ensure_one()

        if not self.key_exist('features'):
            self.get_market_driven_shipping()

        return bool((self['features'] or {}).get('marketDrivenShipping'))

    def get_market_driven_shipping(self):
        self.ensure_one()

        try:
            response = self.execute('query { shop { features { marketDrivenShipping } } }')
            result = self._extract(response, 'data.shop.features', dict) or {}
        except ShopifyApiError as ex:
            if 'marketDrivenShipping' not in str(ex):
                raise
            result = {'marketDrivenShipping': False}

        self.set(features=result)

        return self['features']

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

    def get_product_tags(self):
        self.ensure_one()

        query = '''
            query($cursor: String) {
                productTags(first: 250, after: $cursor) {
                    nodes
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        '''
        tags = []
        cursor = None

        while True:
            response = self.execute(query, variables={'cursor': cursor})
            data = self._extract(response, 'data.productTags', dict) or {}
            tags.extend(data.get('nodes') or [])

            page_info = data.get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')

        self.set(productTags=tags)

        return self['productTags']

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
