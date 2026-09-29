# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class MarketRegionCountry(GqlDict):
    """A market region scoped to a whole country."""

    _gid_name = 'MarketRegionCountry'
    _body = GqlDict._tmpl.MARKET_REGION_COUNTRY_BODY

    def to_delivery_country_vals(self):
        self.ensure_one()
        return {
            'id': self['id'],
            'name': self.name or self.code,
            'code': {'countryCode': self.code, 'restOfWorld': False},
            'provinces': [],
        }
