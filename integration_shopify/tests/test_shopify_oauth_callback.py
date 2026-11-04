# See LICENSE file for full copyright and licensing details.

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch as mock_patch

from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.exceptions import BadRequest

from odoo.tests import tagged
from odoo.tools import mute_logger

from .init_integration_shopify import IntegrationShopifyBase
from ..controllers import shopify_oauth
from ..tools import compute_oauth_hmac


@tagged('post_install', '-at_install', 'test_shopify_oauth_callback')
class TestShopifyOAuthCallback(IntegrationShopifyBase):
    """The OAuth callback must reject everything that did not come from Shopify for the store of the wizard,
    before the client secret is sent anywhere."""

    SECRET = 'test-client-secret'
    SHOP = 'test-store.myshopify.com'

    def setUp(self):
        super().setUp()

        self.wizard = self._create_wizard()
        # The route is wrapped by the environment builder, which needs a real HTTP request
        self.callback = inspect.unwrap(shopify_oauth.ShopifyOAuth.shopify_oauth_callback)

    def _create_wizard(self, integration=None, url='test-store'):
        return self.env['integration.auth.shopify'].create({
            'integration_id': (integration or self.integration).id,
            'url': url,
            'client_id': 'test-client-id',
            'secret_key': self.SECRET,
        })

    def _signed_params(self, wizard=None, **overrides):
        params = {
            'code': 'authorization-code',
            'host': 'dGVzdC1zdG9yZQ',
            'shop': self.SHOP,
            'state': str((wizard or self.wizard).id),
            'timestamp': '1700000000',
        }
        params.update(overrides)
        params['hmac'] = compute_oauth_hmac(params, self.SECRET)

        return params

    def _call(self, params, integration=None, uid=None):
        token_response = MagicMock()
        token_response.json.return_value = {'access_token': 'shpat_test_token'}

        fake_request = SimpleNamespace(
            env=self.env,
            httprequest=SimpleNamespace(args=ImmutableMultiDict(params)),
            session=SimpleNamespace(uid=uid or self.env.uid),
            redirect=lambda url: ('redirect', url),
        )

        with mock_patch.object(shopify_oauth, 'request', fake_request), \
                mock_patch.object(shopify_oauth.requests, 'post', return_value=token_response) as post:
            result = self.callback(
                shopify_oauth.ShopifyOAuth(),
                integration_id=(integration or self.integration).id,
            )

        return result, post

    def _assert_rejected(self, params, **kwargs):
        wizard = kwargs.pop('wizard', self.wizard)

        with mute_logger(shopify_oauth.__name__):
            result, post = self._call(params, **kwargs)

        self.assertIsInstance(result, BadRequest)
        post.assert_not_called()
        self.assertFalse(wizard.key)
        self.assertFalse(wizard.access_granted)

    def test_valid_callback_requests_token(self):
        result, post = self._call(self._signed_params())

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], f'https://{self.SHOP}/admin/oauth/access_token')
        self.assertEqual(post.call_args.kwargs['json'], {
            'client_id': 'test-client-id',
            'client_secret': self.SECRET,
            'code': 'authorization-code',
        })
        self.assertEqual(result, ('redirect', f'/odoo/eci-shopify-authentication/{self.wizard.id}'))
        self.assertEqual(self.wizard.key, 'shpat_test_token')
        self.assertTrue(self.wizard.access_granted)

    def test_foreign_shop_is_rejected(self):
        self._assert_rejected(self._signed_params(shop='evil.example.com'))

    def test_foreign_shop_with_valid_signature_is_rejected(self):
        # Even an attacker who signs the request with a secret of their own cannot redirect the request elsewhere
        for shop in ('evil.example.com', 'test-store.myshopify.com.evil.com', 'other-store.myshopify.com'):
            with self.subTest(shop=shop):
                self._assert_rejected(self._signed_params(shop=shop))

    def test_missing_shop_is_rejected(self):
        params = self._signed_params()
        del params['shop']

        self._assert_rejected(params)

    def test_missing_hmac_is_rejected(self):
        params = self._signed_params()
        del params['hmac']

        self._assert_rejected(params)

    def test_wrong_hmac_is_rejected(self):
        params = self._signed_params()
        params['hmac'] = 'a' * 64

        self._assert_rejected(params)

    def test_non_ascii_hmac_is_rejected(self):
        params = self._signed_params()
        params['hmac'] = 'é' * 64

        self._assert_rejected(params)

    def test_tampered_parameter_is_rejected(self):
        params = self._signed_params()
        params['code'] = 'another-code'

        self._assert_rejected(params)

    def test_wizard_without_secret_is_rejected(self):
        self.wizard.secret_key = False
        params = self._signed_params()

        self._assert_rejected(params)

    def test_wizard_of_another_integration_is_rejected(self):
        other_integration = self.integration.copy({'name': 'Other Shopify integration'})

        self._assert_rejected(self._signed_params(), integration=other_integration)

    def test_wizard_of_another_user_is_rejected(self):
        self._assert_rejected(self._signed_params(), uid=self.env.uid + 1)

    def test_unknown_or_malformed_state_is_rejected(self):
        for state in ('0', '999999999', 'abc', '', '-1'):
            with self.subTest(state=state):
                self._assert_rejected(self._signed_params(state=state))
