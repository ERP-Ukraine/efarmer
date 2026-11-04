# See LICENSE file for full copyright and licensing details.

from odoo.tests import Form, tagged

from .init_integration_shopify import IntegrationShopifyBase


@tagged('post_install', '-at_install', 'test_shopify_auth_wizard')
class TestShopifyAuthWizard(IntegrationShopifyBase):
    """Switching the authentication method in the connection wizard after Reset Credentials."""

    def _open_wizard_form(self, **settings):
        """Open the wizard form the way a connected store opens it, then press Reset Credentials."""
        integration = self.integration
        integration.set_settings_value('url', 'awesome-shop')
        for key, value in settings.items():
            integration.set_settings_value(key, value)
        integration.set_settings_value('access_granted', 'True')

        wizard = integration.create_auth_wizard()
        wizard.reset_credentials()

        view = self.env.ref('integration_shopify.integration_auth_shopify_form_authentication')

        return Form(wizard, view=view)

    def test_basic_to_oauth_keeps_shop_id_and_drops_basic_secret(self):
        """The Basic API secret is not the OAuth client secret, so it must not be carried over, while the
        Shop ID is known and stays. Client ID is never collected by Basic and has to be typed in."""
        form = self._open_wizard_form(
            use_oauth='', key='shpat_basic_token', secret_key='basic_api_secret', client_id='',
        )
        self.assertFalse(form.use_oauth)

        form.use_oauth = True

        self.assertEqual(form.url, 'awesome-shop')
        self.assertFalse(form.client_id)
        self.assertFalse(form.secret_key, 'The Basic API secret must not be offered as the OAuth client secret.')
        self.assertTrue(form.application_name)
        self.assertTrue(form.redirect_url)
        self.assertTrue(form.access_scopes)

    def test_oauth_credentials_survive_switching_back_and_forth(self):
        """When Client ID is already known the stored OAuth credentials are kept on any switch."""
        form = self._open_wizard_form(
            use_oauth='True', key='shpca_oauth_token', secret_key='oauth_client_secret', client_id='oauth_client_id',
        )

        form.use_oauth = False
        form.use_oauth = True

        self.assertEqual(form.url, 'awesome-shop')
        self.assertEqual(form.client_id, 'oauth_client_id')
        self.assertEqual(form.secret_key, 'oauth_client_secret')
