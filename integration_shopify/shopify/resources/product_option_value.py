# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class ProductOptionValue(GqlDict):

    _gid_name = 'ProductOptionValue'
    _body = GqlDict._tmpl.PRODUCT_OPTION_VALUE_BODY
