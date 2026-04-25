# See LICENSE file for full copyright and licensing details.

from .. import STORAGE
from ....shopify.resources.product import Product as Product_


class Product(Product_):

    def get_by_ids(self, ids: list, body: str = None) -> list:
        data = [STORAGE['product'][str(x)] for x in ids]
        return [self.new(**vals) for vals in data]

    def get_by_pk(self, pk: int, body: str = None, **kw):
        return self.set(**STORAGE['product'][str(pk)])
