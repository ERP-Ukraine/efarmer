# See LICENSE file for full copyright and licensing details.

import json
import requests

from odoo import _, models, release
from odoo.exceptions import ValidationError
from json.decoder import JSONDecodeError


ECOSYSTEM_MODULES = [
    'integration',
    'integration_magento2',
    'integration_prestashop',
    'integration_shopify',
    'integration_woocommerce',
    'printnode_base',
    'printnode_pos',
    'zpl_label_designer',
    'zpl_label_designer_printnode',
    'delivery_myparcel',
    'quickbooks_sync_online',
]


class EcosystemSubscriptionStatus(models.AbstractModel):
    _name = 'ecosystem.subscription.status'
    _description = 'Update Ecosystem Subscription Status'

    def _prepare_ecosystem_post_data_for_request(self, key):
        """ Get Ecosystem Subscription data for request. """
        model_ir_config_parameter = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': key,
            'dbuuid': model_ir_config_parameter.get_param('database.uuid'),
            'dbname': self.env.cr.dbname,
            'web_base_url': model_ir_config_parameter.get_param('web.base.url'),
            'version': release.version,
            'vt_ecosystem_modules': self.get_ecosystem_modules(),
        }

    def get_ecosystem_api_key(self):
        """ Get API key for Ecosystem Subscription. """
        return self.env['ir.config_parameter'].sudo().get_param('vt_ecosystem.subscription_key')

    def get_ecosystem_modules(self):
        """ Get technical names of Ecosystem modules. """
        return self.env['ir.module.module'].sudo().search(
            [
                ('name', 'in', ECOSYSTEM_MODULES)
            ]
        ).mapped('name')

    def _check_response(self, response):
        if not response.ok:
            error_message = _('The Ecosystem service is unresponsive, please retry later.')
            try:
                data = response.json()
            except JSONDecodeError:
                raise ValidationError(error_message)

            if not data.get('data') and not data.get('message'):
                raise ValidationError(error_message)

        return response.json()

    def _get_ecosystem_subscription_status(self):
        ecosystem_subscription_key = self.get_ecosystem_api_key()

        ecosystem_api_url = self.env['ir.config_parameter'].sudo().get_param(
            'vt_ecosystem.ecosystem_api_url',
        )
        response = requests.post(
            f'{ecosystem_api_url}/subscriptions/validate',
            data=json.dumps(
                self._prepare_ecosystem_post_data_for_request(ecosystem_subscription_key),
            ),
        )

        response_data = self._check_response(response)
        self._update_ecosystem_subscription_status(response_data)
        return True

    def _update_ecosystem_subscription_status(self, data):
        """ Setting  Ecosystem Subscription data from response

            :param data: Data in JSON format.
                         Expected keys:
                         - subscription_id(int)
                         - start_date(str)
                         - end_date(str)
                         - message(str)
            :return: None.
        """
        model_ir_config_parameter = self.env['ir.config_parameter'].sudo()

        ecosystem_subscription_status = bool(data.get('data', {}).get('subscription_id'))
        last_message = data.get('message')
        subscription_expire_at = data.get('data', {}).get('end_date')

        model_ir_config_parameter.set_param(
            'vt_ecosystem.ecosystem_subscription_status',
            ecosystem_subscription_status,
        )
        model_ir_config_parameter.set_param('vt_ecosystem.last_message', last_message)
        model_ir_config_parameter.set_param(
            'vt_ecosystem.subscription_expire_at',
            subscription_expire_at,
        )
