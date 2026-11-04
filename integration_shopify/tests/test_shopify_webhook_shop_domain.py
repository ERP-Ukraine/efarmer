# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration.controllers.integration_webhook import IntegrationWebhook
from odoo.addons.integration_shopify.controllers.shopify_webhook import ShopifyWebhook


@tagged('post_install', '-at_install')
class TestShopifyWebhookShopDomain(TransactionCase):
    """The webhook shop domain check accepts the integration's own store and nothing else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration = cls.env['sale.integration'].create({
            'name': 'Webhook Shop Domain',
            'type_api': 'shopify',
        })

    def _verify(self, shop_domain, controller_class=ShopifyWebhook):
        headers = {ShopifyWebhook.SHOP_NAME: shop_domain}
        with patch.object(controller_class, '_get_headers', lambda self: headers):
            verified, __ = controller_class._verify_shop_domain(controller_class(), self.integration)

        return verified

    def _set_urls(self, url, original_url=''):
        self.integration.set_settings_value('url', url)
        self.integration.set_settings_value('original_url', original_url)

    def test_short_id_without_original_url_accepts_own_shop(self):
        self._set_urls('awesome-shop')

        self.assertTrue(self._verify('awesome-shop.myshopify.com'))

    def test_short_id_without_original_url_rejects_other_shops(self):
        self._set_urls('awesome-shop')

        for shop_domain in (
            'other-shop.myshopify.com',
            'my-awesome-shop.myshopify.com',
            'awesome-shop.myshopify.com.evil.com',
        ):
            with self.subTest(shop_domain=shop_domain):
                self.assertFalse(self._verify(shop_domain))

    def test_full_domain_in_url_accepts_own_shop(self):
        self._set_urls('https://Awesome-Shop.myshopify.com/')

        self.assertTrue(self._verify('awesome-shop.myshopify.com'))
        self.assertFalse(self._verify('other-shop.myshopify.com'))

    def test_original_url_still_accepted(self):
        # The store ID in `url` may differ from the permanent myshopify domain Shopify reports
        self._set_urls('renamed-shop', original_url='awesome-shop.myshopify.com')

        self.assertTrue(self._verify('awesome-shop.myshopify.com'))
        self.assertTrue(self._verify('renamed-shop.myshopify.com'))
        self.assertFalse(self._verify('other-shop.myshopify.com'))

    def test_rejection_message_names_received_and_expected_domains(self):
        self._set_urls('awesome-shop', original_url='renamed.myshopify.com')

        headers = {ShopifyWebhook.SHOP_NAME: 'other-shop.myshopify.com'}
        with patch.object(ShopifyWebhook, '_get_headers', lambda self: headers):
            verified, message = ShopifyWebhook()._verify_shop_domain(self.integration)

        self.assertFalse(verified)
        self.assertIn('"other-shop.myshopify.com"', message)
        self.assertIn('"awesome-shop"', message)
        self.assertIn('"renamed.myshopify.com"', message)
        self.assertIn('"awesome-shop.myshopify.com"', message)

    def test_rejection_message_when_shop_id_is_empty(self):
        self._set_urls('')

        headers = {ShopifyWebhook.SHOP_NAME: 'other-shop.myshopify.com'}
        with patch.object(ShopifyWebhook, '_get_headers', lambda self: headers):
            verified, message = ShopifyWebhook()._verify_shop_domain(self.integration)

        self.assertFalse(verified)
        self.assertIn('"other-shop.myshopify.com"', message)
        self.assertIn('Shop ID is empty', message)

    def test_domain_check_decides_the_whole_webhook_verification(self):
        # Goes through verify_webhook, so a regression in how the check is wired in cannot hide behind
        # the direct call above. The check runs before webhook lines and signature, hence the reasons below.
        self._set_urls('awesome-shop')
        self.integration.state = 'active'
        controller = ShopifyWebhook()

        def verify(shop_domain):
            headers = {
                ShopifyWebhook.SHOP_NAME: shop_domain,
                ShopifyWebhook.TOPIC_NAME: 'orders/paid',
                'X-Shopify-Hmac-Sha256': 'x',
            }
            with patch.object(ShopifyWebhook, '_get_headers', lambda self: headers):
                return controller.verify_webhook(self.integration)

        __, own_message, __ = verify('awesome-shop.myshopify.com')
        __, other_message, __ = verify('other-shop.myshopify.com')

        self.assertNotIn('invalid shop domain', own_message)
        self.assertIn('invalid shop domain', other_message)

    def test_generic_check_unchanged(self):
        self._set_urls('awesome-shop')

        self.assertFalse(self._verify('awesome-shop.myshopify.com', controller_class=IntegrationWebhook))
