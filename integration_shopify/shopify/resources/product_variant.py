# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead, DeleteMixin
from .product_mixin import ProductMixin


class ProductVariant(ShopifyResourceRead, ProductMixin, DeleteMixin):

    _gid_name = 'ProductVariant'
    _request_name = 'productVariant'
    _body = ShopifyResourceRead._tmpl.PRODUCT_VARIANT_BODY

    MUTATION_DELETE = ShopifyResourceRead._tmpl.MUTATION_PRODUCT_VARIANT_DELETE

    @property
    def external_id(self):
        self.ensure_one()
        return f'{self.product_id}-{self.id}'

    @property
    def product(self):
        self.ensure_one()
        return self._env.Product.set(id=self.product_id)

    @property
    def product_id(self):
        self.ensure_one()

        if not self.key_exist('product'):
            self.read()
            self.raise_if_no_key('product')

        return self.parse_int(self['product']['id'])

    @property
    def price_float(self):
        self.ensure_one()
        return float(self.price or 0)

    @property
    def compare_at_price_float(self):
        self.ensure_one()
        return float(self.compareAtPrice or 0)

    @property
    def inventory_item(self):
        self.ensure_one()
        return self._env.InventoryItem.set(**(self['inventoryItem'] or {}))

    @property
    def selected_options(self):
        self.ensure_one()
        return [self._env.SelectedOption.set(**vals) for vals in (self.selectedOptions or [])]

    @property
    def formatted_selected_options(self):
        self.ensure_one()

        result = []
        for option in self.selected_options:
            # If the attribute name is default and there is only one default value - skip it
            if (
                option.name == self.ATTRIBUTE_DEFAULT_TITLE
                and option.value == self.ATTRIBUTE_DEFAULT_VALUE
            ):
                continue

            result.append((option.name, option.value))

        return result

    def create_gid(self, code: str):
        if isinstance(code, str) and '-' in code:
            code = code.split('-')[-1]
        return super().create_gid(code)

    def get_price(self, has_integration_pricelist: bool = False):
        price = self.price_float

        if has_integration_pricelist:
            compare_at_price = self.compare_at_price_float

            if compare_at_price:
                price = compare_at_price

        return price

    def to_dict(self, simple_identifier: bool = False):
        result = super().to_dict()

        if not result:
            return result

        if simple_identifier:
            result['id'] = self.id_str

        return result

    def get_attribute_values(self, lowercase: bool = False):
        self.ensure_one()

        result = [self.format_attr_value_code(name, value) for name, value in self.formatted_selected_options]

        if lowercase:
            return [x.lower() for x in result]

        return result

    def delete(self):
        self.ensure_one()
        return self.product.bulk_delete_variants([self.id])

    def has_activated_location(self, location_id: str):
        self.ensure_one()
        locations = [x.gid for x in self.inventory_item.locations]

        return self._env.Location.create_gid(location_id) in locations

    def _serialize_variant_for_test(self, *, sku, barcode):
        return {
            'id': self.id_str,
            'name': self.title,
            'barcode': getattr(self, barcode) or '',
            'ref': getattr(self, sku) or '',
            'parent_id': str(self.product_id),
            'skip_ref': False,
            'joint_namespace': False,
        }
