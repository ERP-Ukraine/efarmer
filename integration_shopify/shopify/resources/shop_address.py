# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class ShopAddress(GqlDict):
    """The shop's own address -- not a customer/order MailingAddress.

    Shopify's ShopAddress type has no id of its own, so a pseudo id is set
    just so ensure_one() behaves like it does on every other resource.
    """

    _gid_name = 'ShopAddress'
    _body = GqlDict._tmpl.SHOP_ADDRESS_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def country(self):
        self.ensure_one()
        return self['country'] or ''

    @property
    def country_code(self):
        self.ensure_one()
        return self['countryCodeV2'] or ''

    @property
    def city(self):
        self.ensure_one()
        return self['city'] or ''

    @property
    def zip(self):
        self.ensure_one()
        return self['zip'] or ''

    @property
    def province_code(self):
        self.ensure_one()
        return self['provinceCode'] or ''
