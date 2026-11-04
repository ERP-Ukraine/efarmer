# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import hmac
import logging
import traceback

import requests
from werkzeug.exceptions import BadRequest

from odoo.http import Controller, route, request
from odoo.addons.integration.controllers.utils import build_environment

from ..shopify_api import SHOPIFY
from ..tools import compute_oauth_hmac, is_valid_shop_domain, prepare_shopify_url


_logger = logging.getLogger(__name__)


class ShopifyOAuth(Controller):

    @route(
        [
            f'/integration/<string:dbname>/{SHOPIFY}/<int:integration_id>/oauth',
            f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/oauth',
        ],
        type='http',
        auth='user',
    )
    @build_environment
    def shopify_oauth_callback(self, integration_id: int, **kw):
        # The signature covers every query parameter, so work with the request's own query string
        params = request.httprequest.args.to_dict()
        code = params.get('code')
        shop = params.get('shop')

        # 1. Validate Integration
        integration = request.env['sale.integration'] \
            .browse(integration_id) \
            .exists() \
            .filtered(lambda x: x.is_integration_shopify)

        if not integration:
            return BadRequest('Integration not found')

        # 2. Validate Configuration Wizard: it must belong to this integration and to the logged-in user
        state = params.get('state', '')
        wizard = request.env['integration.auth.shopify'].browse(int(state) if state.isdecimal() else 0).exists()
        if (
            not wizard
            or wizard.integration_id != integration
            or wizard.create_uid.id != request.session.uid
        ):
            return BadRequest('Integration Wizard not found')

        # 3. Validate that the request really comes from Shopify and concerns the store of the wizard.
        # Nothing is sent out and the wizard is left untouched until all checks pass.
        error = self._check_callback_origin(wizard, params)
        if error:
            _logger.warning('Shopify OAuth callback rejected for integration %s: %s', integration.id, error)
            return BadRequest('Invalid OAuth callback request')

        if not code:
            return BadRequest('Authorization code is missing')

        # 4. Prepare Payload Access Token
        payload = {
            'client_id': wizard.client_id,
            'client_secret': wizard.secret_key,
            'code': code,
        }

        # 5. Request Access Token
        try:
            response = requests.post(f'https://{shop}/admin/oauth/access_token', json=payload, timeout=15)
            response.raise_for_status()
        except Exception as e:
            # Store error information in standard error fields
            wizard.write({
                'error_message': str(e),
                'error_traceback': traceback.format_exc(),
                'access_granted': False,
            })
        else:
            # 6. Update Configuration Wizard on success
            wizard.write({
                'key': response.json()['access_token'],
                'access_granted': True,
                'error_message': False,
                'error_traceback': False,
            })

        wizard.save_credentials()

        # Redirect back to authentication form (for both success and error cases)
        return request.redirect(f'/odoo/eci-shopify-authentication/{wizard.id}')

    @staticmethod
    def _check_callback_origin(wizard, params: dict) -> str:
        """
        Check the `shop` and `hmac` parameters of the callback.

        :param wizard: authentication wizard the callback refers to
        :param params: query parameters of the callback request
        :return: reason of the rejection, empty string if the request is valid
        """
        shop = params.get('shop')
        if not is_valid_shop_domain(shop):
            return 'invalid shop'

        if shop != prepare_shopify_url(wizard.url):
            return 'shop does not match the wizard'

        received_hmac = params.get('hmac')
        if not received_hmac or not wizard.secret_key:
            return 'hmac or secret is missing'

        computed_hmac = compute_oauth_hmac(params, wizard.secret_key)
        # Bytes, because compare_digest refuses a str with non-ASCII characters that a forged request may carry
        if not hmac.compare_digest(computed_hmac.encode(), received_hmac.encode()):
            return 'invalid hmac'

        return ''
