# See LICENSE file for full copyright and licensing details.

from .catalog import AbstractCatalog


class MarketCatalog(AbstractCatalog):

    _catalog = 'MarketCatalog'
    _catalog_type = 'MARKET'

    _body = AbstractCatalog._tmpl.MARKET_CATALOG_BODY

    @property
    def markets(self):
        self.ensure_one()
        return [self._env.Market.set(**x) for x in (self['markets'] or [])]

    def _serialize_data(self):
        return {
            'markets': [x._serialize_data() for x in self.markets],
        }
