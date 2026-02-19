# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class Metafield(GqlDict):

    _gid_name = 'Metafield'
    _body = GqlDict._tmpl.METAFIELD_BODY

    @property
    def odoo_key(self):
        self.ensure_one()
        return f'metafields.{self.namespace}.{self.key}'
