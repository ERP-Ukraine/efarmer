# See LICENSE file for full copyright and licensing details.

from .base import GQLEnum


class StatusAbstract(GQLEnum):

    @property
    def mapping(self):
        return {}

    def get_string(self):
        return self.mapping[self.value][0]

    def get_description(self):
        return self.mapping[self.value][1]

    def to_odoo_format(self):
        return self.name

    @classmethod
    def to_list(cls, exclude: list = None) -> list:
        exclude_list = exclude or []

        return [{
            'name': x.name,
            'value': x.value,
            'string': x.get_string(),
            'description': x.get_description(),
        } for x in cls if x.name not in exclude_list]
