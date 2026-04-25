# See LICENSE file for full copyright and licensing details.

import re

from .base import GqlDict


MODEL_NAME_PATTERN = r'model_name=([^&]+)'


class MailingAddress(GqlDict):

    _gid_name = 'MailingAddress'
    _body = GqlDict._tmpl.MAILING_ADDRESS_BODY

    @property
    def model_name(self):
        self.ensure_one()
        match = re.search(MODEL_NAME_PATTERN, self.gid)
        return match.group(1) if match else False

    @property
    def first_name(self):
        self.ensure_one()
        return (self.firstName or '').strip()

    @property
    def last_name(self):
        self.ensure_one()
        return (self.lastName or '').strip()

    @property
    def display_name(self):
        self.ensure_one()
        return ' '.join(filter(None, [self.first_name, self.last_name]))

    @property
    def country_code(self):
        self.ensure_one()
        return self['countryCodeV2'] or ''

    @property
    def state_code(self):
        self.ensure_one()
        return self['provinceCode'] or ''

    @property
    def phone(self):
        self.ensure_one()
        return self['phone'] or ''

    @property
    def company(self):
        self.ensure_one()
        return self['company'] or ''

    @property
    def address1(self):
        self.ensure_one()
        return self['address1'] or ''

    @property
    def address2(self):
        self.ensure_one()
        return self['address2'] or ''

    @property
    def city(self):
        self.ensure_one()
        return self['city'] or ''

    @property
    def zip(self):
        self.ensure_one()
        return self['zip'] or ''

    def to_odoo_format(self):
        self.ensure_one()

        return {
            'id': self.id_str,
            'person_name': self.display_name,
            'phone': self.phone,
            'company_name': self.company,
            'street': self.address1,
            'street2': self.address2,
            'city': self.city,
            'country_code': self.country_code,
            'state_code': self.state_code,
            'zip': self.zip,
        }
