# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum


class MarketType(GQLEnum):

    company_location = 'COMPANY_LOCATION'  # The market applies to the visitor based on the company location.
    location = 'LOCATION'  # The market applies to the visitor based on the location.
    none = 'NONE'  # The market does not apply to any visitor.
    region = 'REGION'  # The market applies to the visitor based on region.

    @property
    def is_company_location(self):
        return self == self.company_location

    @property
    def is_location(self):
        return self == self.location

    @property
    def is_none(self):
        return self == self.none

    @property
    def is_region(self):
        return self == self.region
