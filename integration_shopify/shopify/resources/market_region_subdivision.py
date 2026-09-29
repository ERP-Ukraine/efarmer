# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class MarketRegionSubdivision(GqlDict):
    """A market region scoped to one subdivision (state/province) of a country.

    Shopify has no country-level node for the parent country in this case --
    see `country_gid`.
    """

    _gid_name = 'MarketRegionSubdivision'
    _body = GqlDict._tmpl.MARKET_REGION_SUBDIVISION_BODY

    @property
    def country_code(self):
        self.ensure_one()
        return (self['country'] or {}).get('code')

    @property
    def country_name(self):
        self.ensure_one()
        return (self['country'] or {}).get('name')

    def country_gid(self):
        """A stable synthetic gid for the parent country.

        Picking this subdivision's own id as a stand-in for its country would
        make the id change whenever the region connection's order shifts,
        breaking the external-record key built from it (see
        Market.to_delivery_countries). Digits of the ISO code's own ordinals
        are stable and unique per code.
        """
        self.ensure_one()
        digits = ''.join(str(ord(char)) for char in self.country_code.upper())
        return f'gid://shopify/MarketRegionCountry/{digits}'

    def to_delivery_province_vals(self):
        self.ensure_one()
        return {
            'id': self['id'],
            'name': self.name or self.code,
            'code': self.code,
        }
