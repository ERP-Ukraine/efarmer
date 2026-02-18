# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceUpdate


class PriceList(ShopifyResourceUpdate):

    _gid_name = 'PriceList'
    _request_name = 'priceList'
    _body = ShopifyResourceUpdate._tmpl.PRICELIST_BODY

    BODY_GET_PRICELIST_ITEMS = ShopifyResourceUpdate._tmpl.BODY_GET_PRICELIST_ITEMS

    MUTATION_CREATE = ShopifyResourceUpdate._tmpl.MUTATION_CREATE_PRICE_LIST
    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_PRICE_LIST
    MUTATION_UPDATE_FIXED_PRICES = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_FIXED_PRICES
    MUTATION_UPDATE_FIXED_PRICES_BY_PRODUCT = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_FIXED_PRICES_BY_PRODUCT

    @property
    def currency_code(self):
        self.ensure_one()

        if not self.key_exist('currency'):
            self.read()
            self.raise_if_no_key('currency')

        return self['currency']

    @property
    def parent(self):
        self.ensure_one()
        return self._env.PriceListParent.set(**(self['parent'] or {}))

    def get_all_prices(self, filter_params: str = None):
        """Get prices for a price list with originType=FIXED"""
        self.ensure_one()

        query = 'query { %s(id: "%s") { %s } }' % (
            self._request_name,
            self.gid,
            self.BODY_GET_PRICELIST_ITEMS,
        )

        if filter_params:
            query = query.replace('prices(first: 250', f'prices(first: 250, query: "{filter_params}"')

        response = self.execute(query)
        result = self._extract_response(response, key=f'{self._request_name}.prices')

        query_ = query.replace('prices(first: 250', 'prices(first: 250%s')

        while self.cursor:
            query = query_ % f', after: "{self.cursor}"'

            response = self.execute(query)
            result_ = self._extract_response(response, key=f'{self._request_name}.prices')

            result.extend(result_)

        return [self._env.PriceListPrice.set(**vals) for vals in result]

    def get_product_prices(self, product_id: str):
        self.ensure_one()
        p = self._env.Product.set(id=product_id)
        return self.get_all_prices(filter_params=f'product_id:{p.id}')

    def get_variant_prices(self, variant_id: str):
        self.ensure_one()
        v = self._env.ProductVariant.set(id=variant_id)
        return self.get_all_prices(filter_params=f'variant_id:{v.id}')

    def create(self, *, name: str, currency: str, adjustment_type: str, adjustment_value: float):
        """
        :name: The unique name of the price list, used as a human-readable identifier.
        :currency: Three letter currency code for fixed prices associated with this price list.
        :adjustment_type: The type of price adjustment, such as percentage increase or decrease.
            - PERCENTAGE_INCREASE
            - PERCENTAGE_DECREASE
        :adjustment_value: The value of the price adjustment as specified by the `adjustment_type`.
        """
        response = self.execute(
            self.MUTATION_CREATE,
            variables={
                'input': {
                    'name': name,
                    'currency': currency.upper(),
                    'parent': {
                        'adjustment': {
                            'type': self._normalize_adjustment_type(adjustment_type),
                            'value': adjustment_value,
                        },
                    },
                },
            },
            user_errors_path='data.priceListCreate.userErrors',
        )

        values = self._extract(response, 'data.priceListCreate.priceList', dict)

        return self.new(**values)

    def update(
        self,
        name: str = None,
        currency: str = None,
        adjustment_type: str = None,
        adjustment_value: float = None,
    ):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'id': self.gid,
                'input': {
                    'name': name or self.name,
                    'currency': currency.upper(),
                    'parent': {
                        'adjustment': {
                            'type': adjustment_type.upper(),
                            'value': adjustment_value,
                        },
                    },
                },
            },
            user_errors_path='data.priceListUpdate.userErrors',
        )

        values = self._extract(response, 'data.priceListUpdate.priceList', dict)

        return self.set(**values)

    def update_fixed_prices(self, *, prices_to_add: list = None, variant_ids_to_delete: list = None):
        """
        Updates fixed prices on a price list. You can use the priceListFixedPricesUpdate mutation to set
        a fixed price for specific product variants or to delete prices for variants associated with the price list.
        """
        self.ensure_one()

        pv = self._env.ProductVariant

        # 1. Prepare prices to add data
        prices_to_add_data = []
        for (variant_id, price, compare_at_price, *_) in (prices_to_add or []):
            data = {
                'variantId': pv.create_gid(variant_id),
                'price': {
                    'amount': str(price),
                    'currencyCode': self.currency_code,
                },
            }

            if compare_at_price is not None:
                data['compareAtPrice'] = {
                    'amount': str(compare_at_price),
                    'currencyCode': self.currency_code,
                }

            prices_to_add_data.append(data)

        # 2. Perform mutation
        response = self.execute(
            self.MUTATION_UPDATE_FIXED_PRICES,
            variables={
                'priceListId': self.gid,
                'pricesToAdd': prices_to_add_data,
                'variantIdsToDelete': [pv.create_gid(x) for x in (variant_ids_to_delete or [])],
            },
            # user_errors_path='data.priceListFixedPricesUpdate.userErrors', FIXME: "Only fixed prices can be deleted."
        )

        records = self._extract(response, 'data.priceListFixedPricesUpdate.pricesAdded', list)
        deleted_products = self._extract(response, 'data.priceListFixedPricesUpdate.deletedFixedPriceVariantIds', list)

        return [self._env.PriceListPrice.set(**x) for x in records], deleted_products

    def update_fixed_prices_by_product(self, prices_to_add: list, product_ids_to_delete: list = None):
        """
        Updates the fixed prices for all variants for a product on a price list.
        You can use the priceListFixedPricesByProductUpdate mutation to set or remove
        a fixed price for all variants of a product associated with the price list.
        """
        self.ensure_one()

        pt = self._env.Product

        # 1. Prepare prices to add data
        prices_to_add_data = []
        for (product_id, price, *_) in prices_to_add:
            data = {
                'productId': pt.create_gid(product_id),
                'price': {
                    'amount': str(price),
                    'currencyCode': self.currency_code,
                },
            }

            prices_to_add_data.append(data)

        # 2. Prepare variant ids to delete data
        prices_to_delete_by_product_ids_data = [pt.create_gid(x) for x in (product_ids_to_delete or [])]

        # 3. Perform mutation
        response = self.execute(
            self.MUTATION_UPDATE_FIXED_PRICES_BY_PRODUCT,
            variables={
                'priceListId': self.gid,
                'pricesToAdd': prices_to_add_data,
                'pricesToDeleteByProductIds': prices_to_delete_by_product_ids_data,
            },
            user_errors_path='data.priceListFixedPricesUpdate.userErrors',
        )

        added_for_products = self._extract(
            response, 'data.priceListFixedPricesByProductUpdate.pricesToAddProducts.id', list,
        )

        deleted_for_products = self._extract(
            response, 'data.priceListFixedPricesByProductUpdate.pricesToDeleteProducts.id', list,
        )

        return added_for_products, deleted_for_products
