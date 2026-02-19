# See LICENSE file for full copyright and licensing details.

import re
import urllib

from odoo import api, models, fields

from ..shopify_api import REQUIRED_SCOPES
from ..shopify.shopify_graphql import ShopifyGraphQL
from ..tools import prepare_shopify_url


class ShopifyAccessScopeLine(models.TransientModel):
    _name = 'shopify.access.scope.line'
    _description = 'Shopify Access Scope Line'

    name = fields.Char(
        string='Name',
    )
    is_missed = fields.Boolean(
        string='Missed',
    )
    integration_auth_shopify_id = fields.Many2one(
        comodel_name='integration.auth.shopify',
        ondelete='cascade',
    )


class IntegrationAuthShopify(models.TransientModel):
    _name = 'integration.auth.shopify'
    _inherit = 'integration.auth.abstract'
    _description = 'Shopify Integration Authentication'

    state = fields.Selection(
        selection=[
            ('authentication', 'Authentication'),
            ('authorization', 'Authorization'),
        ],
        string='State',
        default='authentication',
    )

    use_oauth = fields.Boolean(
        string='Use OAuth',
        default=True,
    )

    client_id = fields.Char(
        string='Client ID',
    )

    secret_key = fields.Char(
        string='Secret Key',
    )

    application_name = fields.Char(
        string='Application Name',
        compute='_compute_application_data',
    )
    redirect_url = fields.Char(
        string='Redirect URL',
        compute='_compute_application_data',
    )
    access_scopes = fields.Char(
        string='Access Scopes',
        compute='_compute_application_data',
    )
    configuration_scope_ids = fields.One2many(
        comodel_name='shopify.access.scope.line',
        inverse_name='integration_auth_shopify_id',
        string='Access Scopes Lines',
    )

    is_valid_access_scopes = fields.Boolean(
        string='Proven Access Scopes',
        compute='_compute_is_valid_access_scopes',
    )

    authentication_redirected = fields.Boolean(
        string='OAuth Redirect Triggered',
        default=False,
        help='Set to True when the user is redirected to Shopify for authentication.',
    )

    @api.depends('configuration_scope_ids')
    def _compute_is_valid_access_scopes(self):
        for rec in self:
            value = True

            if rec.configuration_scope_ids:
                value = not any(rec.configuration_scope_ids.mapped('is_missed'))

            rec.is_valid_access_scopes = value

    @api.depends('url', 'use_oauth', 'client_id')
    def _compute_application_data(self):
        for rec in self:
            if rec.use_oauth:
                integration = rec.integration_id

                name = integration.name

                if re.search(r'shopify', name, flags=re.I):
                    name = re.sub(r'shopify', 'Sh0pify', name, flags=re.I)

                rec.application_name = f'{name}: Odoo Integration'
                rec.access_scopes = ','.join(REQUIRED_SCOPES)
                rec.redirect_url = integration._prepare_shopify_oauth_redirect_url()
            else:
                rec.application_name = False
                rec.redirect_url = False
                rec.access_scopes = False

    def set_authentication_state(self):
        self.state = 'authentication'

    def set_authorization_state(self):
        self.state = 'authorization'

    # Open Form

    def open_form_authentication(self):
        self.ensure_one()
        self.set_authentication_state()
        return self.open_form()

    def open_form_authorization(self):
        self.ensure_one()

        self.set_authorization_state()

        action = self.env.ref('integration_shopify.action_view_shopify_integration_authorization').read()[0]
        action['res_id'] = self.id

        return action

    # Request for Authentication

    def connect_to_shopify_oauth(self):
        self.ensure_one()
        self.env.registry.clear_cache()

        self.authentication_redirected = True

        return {
            'type': 'ir.actions.act_url',
            'url': self._build_application_oauth_link(),
            'target': 'new',
        }

    # Save Credentials

    def save_credentials(self, **kw):
        self.ensure_one()

        integration = self.integration_id

        integration.set_settings_value('url', self.url)
        integration.set_settings_value('key', self.key)

        integration.set_settings_value('client_id', self.client_id)
        integration.set_settings_value('secret_key', self.secret_key)

        integration.set_settings_value('use_oauth', str(self.use_oauth))
        integration.set_settings_value('access_granted', str(self.access_granted))

        for key, value in kw.items():
            integration.set_settings_value(key, value)

        return self.close_form()

    # Private Methods

    def _build_scope_lines(self):
        self.ensure_one()
        self.configuration_scope_ids.unlink()

        adapter = self.integration_id.adapter

        adapter_scopes = adapter.shop.get_access_scopes()
        all_scopes = set([*adapter_scopes, *REQUIRED_SCOPES])

        vals_list = []
        for scope in all_scopes:
            if scope not in REQUIRED_SCOPES:
                continue

            vals = {
                'name': ' '.join(map(lambda x: x.capitalize(), scope.split('_'))),
                'is_missed': scope not in adapter_scopes,
                'integration_auth_shopify_id': self.id,
            }
            vals_list.append(vals)

        self.env['shopify.access.scope.line'].create(vals_list)

    def _build_application_oauth_link(self) -> str:
        params = {
            'client_id': self.client_id,
            'scope': self.access_scopes,
            'redirect_uri': self.redirect_url,
            'state': self.id,
        }
        shop = prepare_shopify_url(self.url)
        kw = urllib.parse.urlencode(params)

        return f'https://{shop}/admin/oauth/authorize?{kw}'

    def _build_and_test_client_from_wizard(self):
        self.ensure_one()

        gql = ShopifyGraphQL(
            self.url,
            self.key,
            self.integration_id._get_graphql_version(),
            True,
        )

        shop = gql.Shop
        shop.init()

        return bool(shop)
