# See LICENSE file for full copyright and licensing details.

from ....shopify.resources.shop import Shop as Shop_


class Shop(Shop_):

    def country_code(self):
        return self['billingAddress']['countryCodeV2']

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
            'billingAddress': {
                'country': 'Poland',
                'company': None,
                'countryCodeV2': 'PL',
                'formatted': [
                    'Miczkewicza 10',
                    '01-571 Warszawa',
                    'Polska'
                ]
            },
            'productTags': {
                'nodes': [
                    'car',
                    'cat'
                ]
            }
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
