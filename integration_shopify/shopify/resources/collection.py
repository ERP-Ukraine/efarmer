# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead, CreateMixin


class Collection(ShopifyResourceRead, CreateMixin):

    _gid_name = 'Collection'
    _request_name = 'collection'
    _body = ShopifyResourceRead._tmpl.COLLECTION_BODY

    MUTATION_CREATE = ShopifyResourceRead._tmpl.MUTATION_COLLECTION_CREATE

    def create(self, name: str):
        response = self.execute(
            self.MUTATION_CREATE,
            variables={
                'input': {
                    'title': name,
                }
            },
            user_errors_path='data.collectionCreate.userErrors',
        )

        result = self._extract(response, 'data.collectionCreate.collection', dict)

        return self.new(**result)

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'name': self.title,
        }
