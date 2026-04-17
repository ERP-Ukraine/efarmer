# See LICENSE file for full copyright and licensing details.

# from . import InventoryItem
from .base import GqlDict


class InventoryLevel(GqlDict):

    _gid_name = 'InventoryLevel'
    _body = GqlDict._tmpl.INVENTORY_LEVEL_BODY

    def _set_gid(self, value):
        gid = super()._set_gid(value)

        item_id = self.parse_int(value, index=1)
        if item_id:
            gid = f'{gid}?inventory_item_id={item_id}'

        self._dict['id'] = gid

        return self['id']

    def __repr__(self):
        id_ = self.gid.split('/', maxsplit=1)[-1] if self.gid else self.id
        return f'{self._gid_name}({id_})'

    @property
    def location(self):
        self.ensure_one()
        return self._env.Location.set(**(self['location'] or {}))

    @property
    def item(self):
        self.ensure_one()
        return self._env.InventoryItem.set(**(self['item'] or {}))

    @property
    def variant(self):
        self.ensure_one()
        return self.item.variant

    def get_quantity(self):
        self.ensure_one()
        return sum(x['quantity'] for x in self.quantities)
