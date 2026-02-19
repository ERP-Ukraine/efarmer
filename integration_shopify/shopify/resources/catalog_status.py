# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum


class CatalogStatus(GQLEnum):

    active = 'ACTIVE'
    archived = 'ARCHIVED'
    draft = 'DRAFT'

    @property
    def is_active(self):
        return self == self.active

    @property
    def is_archived(self):
        return self == self.archived

    @property
    def is_draft(self):
        return self == self.draft
