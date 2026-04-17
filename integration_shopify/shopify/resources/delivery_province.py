# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryProvince(GqlDict):

    _gid_name = 'DeliveryProvince'
    _body = GqlDict._tmpl.DELIVERY_PROVINCE_BODY

    @property
    def external_reference(self):
        return f'{self.country_code}_{self.code}'

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'name': self.name,
            'external_reference': self.external_reference,
        }
