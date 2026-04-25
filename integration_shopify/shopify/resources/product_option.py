# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class ProductOption(GqlDict):

    _gid_name = 'ProductOption'
    _body = GqlDict._tmpl.PRODUCT_OPTION_BODY

    @property
    def option_values(self):
        self.ensure_one()
        return [self._env.ProductOptionValue.set(**x) for x in (self['optionValues'] or [])]
