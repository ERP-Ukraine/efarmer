# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryProfileLocationGroup(GqlDict):

    _gid_name = 'DeliveryProfileLocationGroup'
    _body = GqlDict._tmpl.DELIVERY_PROFILE_LOCATION_GROUP_BODY

    @property
    def delivery_zones(self):
        self.ensure_one()
        return [self._env.DeliveryZone.set(**x['zone']) for x in (self['locationGroupZones'] or [])]

    def get_countries(self):
        self.ensure_one()
        return [x.delivery_countries for x in self.delivery_zones]
