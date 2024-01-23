# See LICENSE file for full copyright and licensing details.

import binascii
import os


from odoo import fields, models

# API keys support
API_KEY_SIZE = 20  # in bytes


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ecosystem_subscription_expiration_date = fields.Char(
        config_parameter='vt_ecosystem.subscription_expire_at',
        string='VentorTech Ecosystem expiration date',
        help='VentorTech Ecosystem expiration date',
    )

    ecosystem_subscription_key = fields.Char(
        config_parameter='vt_ecosystem.subscription_key',
        string='VentorTech Ecosystem Subscription Key',
        help='The key for VentorTech Ecosystem',
    )

    ecosystem_subscription_message = fields.Char(
        config_parameter='vt_ecosystem.last_message',
        string='VentorTech Ecosystem message',
        help='VentorTech Ecosystem message',
    )

    ecosystem_subscription_status = fields.Boolean(
        config_parameter='vt_ecosystem.subscription_status',
        string='VentorTech Ecosystem Subscription Status',
        help='VentorTech Ecosystem subscription status',
    )

    integration_api_key = fields.Char(
        string='Integration API Key',
        compute='_compute_integration_api_key',
        help='API key for the integration.',
    )

    def _compute_integration_api_key(self):
        """ Compute API key for the installed integration. """
        for record in self:
            record.integration_api_key = self.get_integration_api_key()

    def generate_integration_api_key(self):
        """ Generate API key for the installed integration. """
        api_key = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
        self.env['ir.config_parameter'].sudo().set_param('integration.integration_api_key', api_key)
        return self._compute_integration_api_key()

    def get_values(self):
        """ Get values for the installed integration. """
        res = super(ResConfigSettings, self).get_values()

        res.update(
            integration_api_key=self.get_integration_api_key(),
        )

        return res

    def get_integration_api_key(self):
        """ Get API key for the installed integration. """
        return self.env['ir.config_parameter'].sudo().get_param('integration.integration_api_key')

    def get_ecosystem_subscription_status(self):
        """ Get Ecosystem subscription status """
        return self.env['ir.config_parameter'].sudo().get_param('vt_ecosystem.subscription_status')

    def update_ecosystem_subscription_info(self):
        self.env['ecosystem.subscription.status']._get_ecosystem_subscription_status()

    def set_values(self):
        previous_group_ecosystem_subscription_key = self.env['ir.config_parameter'].sudo() \
            .get_param('vt_ecosystem.subscription_key')
        res = super(ResConfigSettings, self).set_values()
        if self.ecosystem_subscription_key and \
                previous_group_ecosystem_subscription_key != self.ecosystem_subscription_key:
            self.sudo().update_ecosystem_subscription_info()
        return res
