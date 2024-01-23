# See LICENSE file for full copyright and licensing details.

from ...shopify_api import METAFIELDS_NAME
from odoo.addons.integration.models.fields import ReceiveFields


class ReceiveFieldsShopify(ReceiveFields):

    def _get_value(self, field_name):
        if not field_name.startswith(f'{METAFIELDS_NAME}.'):
            return getattr(self.external_obj, field_name, None)

        meta_fields = self.external_obj.metafields()
        __, namespace, key = field_name.split('.')

        meta_field = list(filter(
            lambda x: x.key == key and x.namespace == namespace, meta_fields))
        value = meta_field and meta_field[0].value or None
        return value
