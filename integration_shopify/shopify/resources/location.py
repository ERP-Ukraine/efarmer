# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class Location(ShopifyResourceRead):

    _gid_name = 'Location'
    _request_name = 'location'
    _body = ShopifyResourceRead._tmpl.LOCATION_BODY

    LOCATION_GET_STOCK_LEVELS_BODY = ShopifyResourceRead._tmpl.LOCATION_GET_STOCK_LEVELS_BODY

    @property
    def active(self):
        return self.isActive

    def get_inventory_levels(self):
        self.ensure_one()

        query = 'query { %s(id: "%s") { %s } }' % (
            self._request_name,
            self.gid,
            self.LOCATION_GET_STOCK_LEVELS_BODY,
        )

        response = self.execute(query)
        result = self._extract_response(response, key=f'{self._request_name}.inventoryLevels')

        query_ = query.replace('inventoryLevels(first: 250', 'inventoryLevels(first: 250%s')

        while self.cursor:
            query = query_ % f', after: "{self.cursor}"'

            response = self.execute(query)
            result_ = self._extract_response(response, key=f'{self._request_name}.inventoryLevels')

            result.extend(result_)

        return [self._env.InventoryLevel.set(**vals) for vals in result]

    def to_odoo_format(self):
        return {
            'id': self.id_str,
            'name': self.name,
        }
