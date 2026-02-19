# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryMethod(GqlDict):

    _gid_name = 'DeliveryMethod'
    _body = GqlDict._tmpl.DELIVERY_METHOD_BODY

    SHOPIFY_SHIPPING_PREFIX = 'shopify-shipping-'

    @property
    def is_valid(self):
        return bool(self.name and self.code)

    @property
    def name(self):
        return self.presentedName or self.code

    @property
    def code(self):
        return self.serviceCode

    @property
    def method_type(self):
        self.ensure_one()
        return self._env.DeliveryMethodType(self['methodType'])

    def to_odoo_format(self, to_tuple=False):
        self.ensure_one()

        formatted_code = self.format_delivery_code(self.name, self.code)

        data = (('id', formatted_code), ('name', self.name))

        if to_tuple:
            return data

        return dict(data)

    def format_delivery_code(self, title: str, code: str) -> str:
        name = f'{title.title()} {code.title()}'  # TODO: get rid of this wierd formatting
        return f'{self.SHOPIFY_SHIPPING_PREFIX}{name}'
