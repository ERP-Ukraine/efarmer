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

        conditions = self['conditions']
        regions_condition = conditions.get('regionsCondition') or {}
        regions = regions_condition.get('regions') or {}

        return regions

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
