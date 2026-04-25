# See LICENSE file for full copyright and licensing details.

from .resources_patch import (
    ShopLocale,
    Shop,
    Product,
    Order,
)

from ...shopify_api import ShopifyAPIClient
from ...shopify.shopify_graphql import ShopifyGraphQL


class ShopifyGraphQLPatchTest(ShopifyGraphQL):

    def execute(self, *args, **kw):
        """TODO"""
        return {}


ShopifyGraphQLPatchTest.update_class(**{
    ShopLocale._gid_name: ShopLocale,
    Shop._gid_name: Shop,
    Product._gid_name: Product,
    Order._gid_name: Order,
})


class ShopifyAPIClientPatchTest(ShopifyAPIClient):

    def __init__(self, settings):
        self._integration_id = None
        self._integration_name = None
        self._settings = settings

        self.gql = ShopifyGraphQLPatchTest(
            'shopifytestsite',
            'shpat_blablablablablablabla',
            '2025-10',
            True,  # Debug mode
        )

        self._ShopifyAPIClient__shop = self.gql.Shop

    def get_payment_methods(self):
        return [
            {'id': 'shopify-payment-bogus', 'name': 'bogus'},
            {'id': 'shopify-payment-manual_in_shopify_test', 'name': 'manual_in_shopify_test'},
            {'id': 'shopify-payment-gift_card', 'name': 'gift_card'},
            {'id': 'shopify-payment-Not_Defined', 'name': 'shopify-payment-Not_Defined'},
        ]

    def get_categories(self):
        return [
            {'id': '440313119012', 'name': 'Classic'},
            {'id': '440312267044', 'name': 'OUTLET'},
        ]

    def get_attributes(self):
        return [
            {'id': 'shopify-attribute-Instrument color', 'name': 'Instrument color'},
            {'id': 'shopify-attribute-Neck material', 'name': 'Neck material'},
        ]

    def get_attribute_values(self):
        return [
            {
                'id': 'shopify-attribute-value-Instrument color-Gold',
                'id_group': 'shopify-attribute-Instrument color',
                'id_group_name': 'Instrument color',
                'name': 'Gold',
            },
            {
                'id': 'shopify-attribute-value-Instrument color-Bronze',
                'id_group': 'shopify-attribute-Instrument color',
                'id_group_name': 'Instrument color',
                'name': 'Bronze',
            },
            {
                'id': 'shopify-attribute-value-Neck material-Boxwood',
                'id_group': 'shopify-attribute-Neck material',
                'id_group_name': 'Neck material',
                'name': 'Boxwood',
            },
            {
                'id': 'shopify-attribute-value-Neck material-Wood',
                'id_group': 'shopify-attribute-Neck material',
                'id_group_name': 'Neck material',
                'name': 'Wood',
            },
        ]
