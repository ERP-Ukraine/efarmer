# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryZone(GqlDict):

    _gid_name = 'DeliveryZone'
    _body = GqlDict._tmpl.DELIVERY_ZONE_BODY

    @property
    def delivery_countries(self):
        self.ensure_one()
        return [self._env.DeliveryCountry.set(**x) for x in (self['countries'] or [])]
