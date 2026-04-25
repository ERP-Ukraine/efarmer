# See LICENSE file for full copyright and licensing details.

from ....shopify.resources.shop_locale import ShopLocale as ShopLocale_


class ShopLocale(ShopLocale_):

    def fetch_all(self):

        result = [
            {
                'locale': 'be',
                'name': 'Belarusian',
                'primary': False,
                'published': True
            },
            {
                'locale': 'en',
                'name': 'English',
                'primary': True,
                'published': True
            },
            {
                'locale': 'pl',
                'name': 'Polish',
                'primary': False,
                'published': True
            }
        ]

        return [self._new(**x) for x in result]
