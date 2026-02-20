# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class DeliveryMethod(GqlDict):

    _gid_name = 'DeliveryMethod'
    _body = GqlDict._tmpl.DELIVERY_METHOD_BODY

    SHOPIFY_SHIPPING_PREFIX = 'shopify-shipping-'

    @property
    def is_valid(self):
        is_valid_method = not self.method_type.is_none
        return bool(is_valid_method and self.name and self.code)

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

    def to_odoo_format(self, to_tuple: bool = False):
        self.ensure_one()

        if not self.is_valid:
            return False

        method_type = self.method_type

        # 1. Format the method as a standard type if no-shipping-type
        if not method_type.is_shipping:
            data = self._to_odoo_format_from_type(method_type.value)

            # 1.1 Since serialization was triggered from a specified delivery provider,
            # add the original delivery method name instead of a common one, for example:
            # {'id': pick_up, 'name': 'Pick up by a customer'} --> {'id': pick_up, 'name': 'John Doe'}
            data['name'] = self.name

            if to_tuple:
                data = tuple(data.items())
            return data

        # 2. Format shipping method as a specific delivery provider
        formatted_code = self.format_delivery_code(self.name, self.code)

        data = (('id', formatted_code), ('name', self.name))

        if to_tuple:
            return data

        return dict(data)

    def _to_odoo_format_from_type(self, method_type: str, to_tuple: bool = False):
        if not method_type:
            return False

        method_type = self._env.DeliveryMethodType(method_type)

        # 1. Format as a specific delivery provider
        if method_type.is_shipping:
            return self.to_odoo_format(to_tuple)

        if method_type.is_none:
            return False

        # 2. Format as a standard type
        data = (('id', method_type.value), ('name', method_type.get_description()))

        if to_tuple:
            return data

        return dict(data)

    def format_delivery_code(self, code: str, title: str = '') -> str:
        name = f'{title.title()} {code.title()}'  # TODO: get rid of this wierd formatting
        return f'{self.SHOPIFY_SHIPPING_PREFIX}{name}'
