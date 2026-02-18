# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import requests
from werkzeug.exceptions import BadRequest

from odoo.http import Controller, route, request
from odoo.addons.integration.controllers.utils import build_environment

from ..shopify_api import SHOPIFY


class ShopifyOAuth(Controller):

    @route(f'/<string:dbname>/integration/{SHOPIFY}/<int:integration_id>/oauth', type='http', auth='user')
    @build_environment
    def shopify_oauth_callback(self, integration_id: int, code: str, shop: str, state: int, **kw):
        # 1. Validate Integration
        integration = request.env['sale.integration'] \
            .browse(integration_id) \
            .exists() \
            .filtered(lambda x: x.is_integration_shopify)

        if not integration:
            return BadRequest('Integration not found')

        # 2. Validate Configuration Wizard
        wizard = request.env['integration.auth.shopify'].browse(int(state)).exists()
        if not wizard:
            return BadRequest('Integration Wizard not found')

        # 3. Prepare Payload Access Token
        payload = {
            'client_id': wizard.client_id,
            'client_secret': wizard.secret_key,
            'code': code,
        }

        # 4. Request Access Token
        try:
            response = requests.post(f'https://{shop}/admin/oauth/access_token', json=payload, timeout=15)
            response.raise_for_status()
        except Exception as e:
            import traceback
            # Store error information in standard error fields
            wizard.write({
                'error_message': str(e),
                'error_traceback': traceback.format_exc(),
                'access_granted': False,
            })
        else:
            # 5. Update Configuration Wizard on success
            wizard.write({
                'key': response.json()['access_token'],
                'access_granted': True,
                'error_message': False,
                'error_traceback': False,
            })

        wizard.save_credentials()

        # Redirect back to authentication form (for both success and error cases)
        return request.redirect(f'/odoo/eci-shopify-authentication/{wizard.id}')
