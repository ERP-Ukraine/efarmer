# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class TranslatableContent(GqlDict):

    _gid_name = 'TranslatableContent'
    _body = GqlDict._tmpl.TRANSLATABLE_CONTENT_BODY

    def __repr__(self):
        return f'{self._gid_name}({self["locale"]}, {self["key"]})'

    def __bool__(self):
        return bool(self['digest'])
