# See LICENSE file for full copyright and licensing details.

from .base import GqlDict, ReadMixin


class Catalog(GqlDict, ReadMixin):
    """This is an GQL Interface, not a real object."""

    _gid_name = 'Catalog'
    _request_name = 'catalog'
    _body = GqlDict._tmpl.CATALOG_BODY

    @property
    def status(self):
        self.ensure_one()
        return self._env.CatalogStatus(self['status'])

    @property
    def is_active(self):
        return self.status.is_active

    @property
    def price_list(self):
        self.ensure_one()
        return self._env.PriceList.set(**(self['priceList'] or {}))

    @property
    def publication(self):
        self.ensure_one()
        return self._env.Publication.set(**(self['publication'] or {}))

    def _read(self) -> None:
        self.ensure_one()

        body = 'query { %s(id: "%s") { %s } }' % (self._request_name, self.gid, self.default_body())

        response = self._env.execute(body)
        data = self._extract(response, f'data.{self._request_name}', dict)

        self.set(**data)

    def _get_batch(self, arguments: str = None):
        body_ = 'query { %s(first: 250) { nodes { %s } } }'

        if arguments:
            body_ = body_.replace('(first: 250', f'(first: 250, {arguments}')

        body = body_ % (self._request_name_plural, self.default_body())

        response = self._env.execute(body)
        data = self._extract(response, f'data.{self._request_name_plural}.nodes', list)

        return [self._new(**x) for x in data]


class AbstractCatalog(Catalog):
    """
    Abstract catalog class.  Use it for creating new catalog types like
    MarketCatalog, CompanyLocationCatalog, AppCatalog etc.
    """

    _catalog = None
    _catalog_type = None

    def __repr__(self):
        return f'{self._catalog}({self.id})'

    def create_gid(self, *args, **kw) -> str:
        value = super().create_gid(*args, **kw)
        return value.replace('Catalog', self._catalog)

    @property
    def currency_code(self):
        self.ensure_one()
        return self.price_list.currency_code

    def get_type(self):
        return self._catalog_type

    def read(self, *args, **kw):
        return self._read()

    def fetch_all(self):
        result = self._get_batch(arguments=f'type: {self.get_type()}')
        return [self._new(**x.to_dict()) for x in result]

    def to_odoo_format(self):
        return {
            'code': self.id_str,
            'name': self.title,
            'catalog_type': self.get_type(),
            'status': self.status.value,
            'pricelist_data': self.price_list.to_dict(),
            'publication_data': self.publication.to_dict(),
            'market_data': self._serialize_data(),
        }
