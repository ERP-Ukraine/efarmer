# See LICENSE file for full copyright and licensing details.

import logging

from .base import ShopifyResourceRead


_logger = logging.getLogger(__name__)


class Taxonomy(ShopifyResourceRead):
    _gid_name = 'Taxonomy'
    _request_name = 'taxonomy'
    _body = ShopifyResourceRead._tmpl.TAXONOMY_BODY

    TAXONOMY_GET_CATEGORIES_BODY = ShopifyResourceRead._tmpl.TAXONOMY_GET_CATEGORIES_BODY

    def get_categories(self):
        """Fetch all taxonomy categories across all levels.

        Shopify's taxonomy returns only root categories by default.
        We first fetch roots, then use 'descendantsOf' for each root to get
        all children at every level.
        """
        root_categories = self._fetch_paginated()
        fetched_categories = list()

        for root_category in root_categories:
            fetched_categories.extend(self._fetch_paginated(root_category['id']))

        all_fetched_categories = root_categories + fetched_categories

        _logger.info('Taxonomy.get_categories(): total=%d', len(all_fetched_categories))
        return [self._env.TaxonomyCategory.set(**cat) for cat in all_fetched_categories]

    def _fetch_paginated(self, category_gid=None):
        """Execute a taxonomy categories query and follow all pagination cursors."""

        categories_body = self.TAXONOMY_GET_CATEGORIES_BODY
        if category_gid:
            categories_body = self.TAXONOMY_GET_CATEGORIES_BODY.replace(
                'categories(first: 250',
                'categories(first: 250, descendantsOf: "%s"' % category_gid,
            )

        query = '{ taxonomy { %s } }' % categories_body

        response = self.execute(query)
        result = list(self._extract_response(response, key='taxonomy.categories'))

        query_ = query.replace('categories(first: 250', 'categories(first: 250%s')

        while self.cursor:
            paged_query = query_ % (', after: "%s"' % self.cursor)

            response = self.execute(paged_query)
            result.extend(self._extract_response(response, key='taxonomy.categories'))

        return result
