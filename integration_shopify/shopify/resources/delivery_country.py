# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryCountry(GqlDict):

    _gid_name = 'DeliveryCountry'
    _body = GqlDict._tmpl.DELIVERY_COUNTRY_BODY

    @property
    def external_reference(self):
        if self.code['restOfWorld']:
            return '*'
        return self.code['countryCode']

    @property
    def provinces(self):
        self.ensure_one()
        return [
            self._env.DeliveryProvince.set(**x, country_code=self.external_reference)
            for x in (self['provinces'] or [])
        ]

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'name': self.name,
            'external_reference': self.external_reference,
        }

    def provinces_to_odoo_format(self):
        self.ensure_one()
        return [x.to_odoo_format() for x in self.provinces]
