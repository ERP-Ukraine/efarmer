# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class Market(ShopifyResourceRead):

    _gid_name = 'Market'
    _request_name = 'market'
    _body = ShopifyResourceRead._tmpl.MARKET_BODY

    @property
    def type(self):
        self.ensure_one()
        return self._env.MarketType(self['type'])

    @property
    def currency_settings(self):
        self.ensure_one()

        currency_settings = self['currencySettings']
        base_currency = currency_settings['baseCurrency'] if currency_settings else {}

        return self._env.CurrencySetting.set(**base_currency)

    @property
    def currency_code(self):
        self.ensure_one()
        return self.currency_settings.currency_code

    @property
    def currency_name(self):
        self.ensure_one()
        return self.currency_settings.currency_name

    @property
    def regions(self):
        self.ensure_one()

        conditions = self['conditions'] or {}
        regions_condition = conditions.get('regionsCondition') or {}
        return regions_condition.get('regions') or []

    def to_delivery_countries(self):
        """Map this market's region conditions onto DeliveryCountry records.

        Market-driven shipping stores destinations on the market, not on
        delivery profiles. Country regions become countries; subdivision
        regions become provinces of their parent country. Aggregating several
        subdivisions under one country is a cross-region concern, so it stays
        here rather than on MarketRegionSubdivision itself.
        """
        self.ensure_one()
        by_code = {}

        for raw_region in self.regions:
            if raw_region.get('__typename') == 'MarketRegionSubdivision':
                subdivision = self._env.MarketRegionSubdivision.set(**raw_region)
                code = subdivision.country_code
                if not code:
                    continue

                entry = by_code.setdefault(code, {
                    'id': subdivision.country_gid(),
                    'name': subdivision.country_name or code,
                    'code': {'countryCode': code, 'restOfWorld': False},
                    'provinces': [],
                })
                if subdivision.country_name:
                    entry['name'] = subdivision.country_name
                entry['provinces'].append(subdivision.to_delivery_province_vals())
                continue

            country = self._env.MarketRegionCountry.set(**raw_region)
            code = country.code
            if not code:
                continue

            entry = by_code.setdefault(code, country.to_delivery_country_vals())
            entry['id'] = country['id']
            if country.name:
                entry['name'] = country.name

        return [self._env.DeliveryCountry.set(**vals) for vals in by_code.values()]

    def to_odoo_format(self):
        return {
            'id': self.id_str,
            'name': self.name,
            'type': self.type.value,
        }

    def _serialize_data(self):
        return {
            'id': self.gid,
            'name': self.name,
            'type': self.type.value,
            'currency_code': self.currency_code,
            'currency_name': self.currency_name,
            'regions': [x['name'] for x in self.regions],
        }
