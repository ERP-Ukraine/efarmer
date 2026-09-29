# See LICENSE file for full copyright and licensing details.

from ....shopify.resources.shop import Shop as Shop_


class Shop(Shop_):

    def get_current(self):

        self.set(**{
            'id': 'gid://shopify/Shop/100500100500',
            'url': 'https://vendevstore2.myshopify.com',
            'name': 'vendevstore2',
            'email': 'ventormailtrap@gmail.com',
            'weightUnit': 'KILOGRAMS',
            'ianaTimezone': 'Europe/Warsaw',
            'timezoneOffset': '+0200',
            'taxesIncluded': False,
            'taxShipping': True,
            'currencyCode': 'PLN',
            'shopAddress': {
                'country': 'Poland',
                'countryCodeV2': 'PL',
                'city': 'Warszawa',
                'zip': '01-571',
                'provinceCode': None,
            },
            'productTags': {
                'nodes': [
                    'car',
                    'cat'
                ]
            },
            'features': {
                'marketDrivenShipping': False,
            },
        })

        return self

    def get_access_scopes(self):

        self.set(accessScopes=[
            'write_fulfillments',
            'read_fulfillments',
            'write_inventory',
            'read_inventory',
            'read_orders',
            'write_products',
            'read_products',
            'write_orders',
            'read_returns',
            'write_returns',
            'write_merchant_managed_fulfillment_orders',
            'read_merchant_managed_fulfillment_orders',
            'read_customers',
            'write_locations',
            'read_locations',
            'read_shipping',
            'write_shipping',
            'read_publications',
            'read_all_orders',
            'unauthenticated_write_customers',
            'unauthenticated_read_customers',
            'unauthenticated_read_customer_tags',
        ])

        return self['accessScopes']
