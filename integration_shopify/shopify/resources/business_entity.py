# See LICENSE file for full copyright and licensing details.

from typing import Union

from .base import ShopifyResourceRead


class BusinessEntity(ShopifyResourceRead):

    _gid_name = 'BusinessEntity'
    _request_name = 'businessEntity'
    _body = ShopifyResourceRead._tmpl.BUSINESS_ENTITY_BODY

    @property
    def _request_name_plural(self):
        return 'businessEntities'

    @property
    def id(self):
        gid = self.gid
        return gid.split('/')[-1] if gid else ''

    @property
    def name(self):
        return self.displayName

    def create_gid(self, value: Union[str, int]) -> str:
        # BusinessEntity IDs may already come as full non-numeric GIDs, e.g.
        # "gid://shopify/BusinessEntity/MTEwMjA2Njf5"
        if isinstance(value, str) and self._gid_name in value:
            return value
        return super().create_gid(value)

    def get_batch(self, *args, **kwargs):
        response = self.execute(
            '{ %s { %s } }' % (self._request_name_plural, self._body)
        )

        data = self._extract(response, f'data.{self._request_name_plural}', list)
        return [self.new(**x) for x in data]

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'name': self.name,
        }
