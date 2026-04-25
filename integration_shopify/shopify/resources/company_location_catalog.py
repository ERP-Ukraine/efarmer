# See LICENSE file for full copyright and licensing details.

from .catalog import AbstractCatalog


class CompanyLocationCatalog(AbstractCatalog):

    _catalog = 'CompanyLocationCatalog'
    _catalog_type = 'COMPANY_LOCATION'

    _body = AbstractCatalog._tmpl.COMPANY_LOCATION_CATALOG_BODY

    def company_locations_data(self) -> list:
        self.ensure_one()
        return self['companyLocations'] or []

    def fetch_all(self):
        result = self._get_batch(arguments='type: COMPANY_LOCATION')
        return [self._new(**x.to_dict()) for x in result]

    def _serialize_data(self):
        return {
            'company_locations': self.company_locations_data(),
        }
