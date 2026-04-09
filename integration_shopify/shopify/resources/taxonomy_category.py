# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class TaxonomyCategory(GqlDict):
    """Shopify taxonomy categories use string-based IDs (e.g. 'ae-2-8-7-2-4')
    instead of numeric ones, so we bypass the standard GID machinery."""

    _gid_name = 'TaxonomyCategory'
    _body = GqlDict._tmpl.TAXONOMY_CATEGORY_BODY

    def __bool__(self):
        return bool(self['id'])

    @property
    def id(self):
        return self.code

    @property
    def id_str(self):
        return self.code

    @property
    def gid(self):
        return self['id'] or ''

    def _set_gid(self, value):
        """Store the raw ID value without integer conversion."""
        self._dict['id'] = str(value) if value else value

    def create_gid(self, value):
        return self._create_gid(self._parse_code(str(value)))

    @staticmethod
    def _parse_code(value):
        """Extract category code from a raw ID or GID string.
        e.g. 'gid://shopify/TaxonomyCategory/ae-2-8-7-2-4' → 'ae-2-8-7-2-4'
        """
        if not value:
            return ''
        return value.rsplit('/', 1)[-1] if '/' in value else value

    @staticmethod
    def _create_gid(code):
        """Create a GID string from a category code."""
        return f'gid://shopify/TaxonomyCategory/{code}' if code else ''

    @property
    def code(self):
        return self._parse_code(self['id'])

    @property
    def parent_code(self):
        return self._parse_code(self['parentId'] or '')

    @property
    def ancestor_codes(self):
        return [self._parse_code(gid) for gid in (self['ancestorIds'] or [])]

    def to_odoo_format(self):
        return {
            'id': self.code,
            'name': self['name'],
            'id_parent': self.parent_code,
            'level': self['level'] or len(self.ancestor_codes),
            'is_archived': self['isArchived'] or False,
            'full_name': self['fullName'] or '',
            'ancestor_codes': self.ancestor_codes,
        }
