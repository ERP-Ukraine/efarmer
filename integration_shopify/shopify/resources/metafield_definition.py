# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class MetafieldDefinition(ShopifyResourceRead):

    _gid_name = 'MetafieldDefinition'
    _request_name = 'metafieldDefinition'
    _body = ShopifyResourceRead._tmpl.METAFIELD_DEFINITION_BODY

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'metafield_code': self.id_str,
            'metafield_name': self.name,
            'metafield_key': self.key,
            'metafield_namespace': self.namespace,
            'metafield_type': self.type['name'],
        }
