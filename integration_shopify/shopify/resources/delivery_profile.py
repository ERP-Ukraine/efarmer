# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class DeliveryProfile(ShopifyResourceRead):

    _gid_name = 'DeliveryProfile'
    _request_name = 'deliveryProfile'
    _body = ShopifyResourceRead._tmpl.DELIVERY_PROFILE_BODY

    @property
    def location_groups(self):
        self.ensure_one()

        return [
            self._env.DeliveryProfileLocationGroup.set(**x['locationGroup'], locationGroupZones=x['locationGroupZones'])
            for x in (self['profileLocationGroups'] or [])
        ]

    def get_countries(self):
        self.ensure_one()
        return list(set(self.flatten_recursive([x.get_countries() for x in self.location_groups])))
