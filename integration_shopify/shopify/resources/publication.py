# See LICENSE file for full copyright and licensing details.

from itertools import zip_longest

from .base import ShopifyResourceUpdate


class Publication(ShopifyResourceUpdate):

    _gid_name = 'Publication'
    _request_name = 'publication'
    _body = ShopifyResourceUpdate._tmpl.PUBLICATION_BODY

    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_PUBLICATION_UPDATE
    PUBLICATION_BODY_GET_PRODUCTS = ShopifyResourceUpdate._tmpl.PUBLICATION_BODY_GET_PRODUCTS

    def _compute_name(self):
        self.ensure_one()
        catalog = self.catalog

        if catalog['title']:
            return catalog.title

        return self['name'] or f'Sales Channel {self.id}'

    @property
    def catalog(self):
        self.ensure_one()
        return self._env.Catalog.set(**(self['catalog'] or {}))

    def get_products(self):
        self.ensure_one()

        query = 'query { %s(id: "%s") { %s } }' % (
            self._request_name,
            self.gid,
            self.PUBLICATION_BODY_GET_PRODUCTS,
        )

        response = self.execute(query)
        result = self._extract_response(response, key=f'{self._request_name}.products')

        query_ = query.replace('products(first: 250', 'products(first: 250%s')

        while self.cursor:
            query = query_ % f', after: "{self.cursor}"'

            response = self.execute(query)
            result_ = self._extract_response(response, key=f'{self._request_name}.products')

            result.extend(result_)

        return [self._env.Product.set(**vals) for vals in result]

    def update(self, *, product_ids_to_include: list = None, product_ids_to_exclude: list = None):
        self.ensure_one()

        pt = self._env.Product

        to_include = [pt.create_gid(x) for x in (product_ids_to_include or [])]
        to_exclude = [pt.create_gid(x) for x in (product_ids_to_exclude or [])]

        # Split by 50 according to GraphQL API limitations
        to_exclude_chunks = [to_exclude[i:i + 50] for i in range(0, len(to_exclude), 50)]

        for to_include_, to_exclude_ in zip_longest([to_include], to_exclude_chunks, fillvalue=[]):
            self._update(to_include_, to_exclude_)

        return True

    def _update(self, product_ids_to_include: list = None, product_ids_to_exclude: list = None):
        if not product_ids_to_include and not product_ids_to_exclude:
            return False

        return self.execute(
            self.MUTATION_UPDATE,
            variables={
                'id': self.gid,
                'input': {
                    'publishablesToAdd': product_ids_to_include,
                    'publishablesToRemove': product_ids_to_exclude,
                },
            },
            user_errors_path='data.publicationUpdate.userErrors',
        )

    def to_odoo_format(self):
        self.ensure_one()

        return dict(
            channel_id=self.id_str,
            channel_name=self._compute_name()
        )
