# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum


class ProductStatus(GQLEnum):

    active = 'ACTIVE'
    archived = 'ARCHIVED'
    draft = 'DRAFT'
    unlisted = 'UNLISTED'

    @property
    def is_active(self):
        return self == self.active

    @property
    def is_archived(self):
        return self == self.archived

    @property
    def is_draft(self):
        return self == self.draft

    @property
    def is_unlisted(self):
        return self == self.unlisted

    @classmethod
    def from_odoo(cls, value: bool) -> str:
        return cls.active.value if value else cls.archived.value
