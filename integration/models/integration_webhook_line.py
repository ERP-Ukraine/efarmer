#  See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class IntegrationWebhookLine(models.Model):
    _name = 'integration.webhook.line'
    _description = 'Integration Webhook Line'

    name = fields.Char(
        string='Name',
        required=True,
    )
    technical_name = fields.Char(
        string='Technical Name',
        required=True,
    )
    controller_method = fields.Char(
        string='Controller Method',
    )
    external_ref = fields.Char(
        string='External ID',
        required=True,
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
    )
    is_active = fields.Boolean(
        string='Mute',
        default=True,
    )
    original_base_url = fields.Char(
        string='Original Base URL',
    )
    controller_route = fields.Char(
        string='Webhook Url',
        compute='_compute_controller_route',
    )
    is_valid_base_url = fields.Boolean(
        string='Is Valid Base Url',
        compute='_compute_is_valid_base_url',
    )

    def action_toggle_active(self):
        self.ensure_one()
        self.is_active = not self.is_active

        if self.is_active:
            message, title = _('The webhook has been activated.'), _('Activate')
        else:
            message, title = _('The webhook has been deactivated.'), _('Deactivate')
        return self.display_integration_notification(message, title=title)

    def action_delete_webhook(self):
        self.ensure_one()
        result = self.integration_id.delete_webhook(self)

        if result is True:
            return self.display_integration_notification(
                _('The webhook has been deleted.'), title=_('Delete Webhook'),
            )

        return result

    def _compute_controller_route(self):
        for rec in self:
            method = rec.controller_method
            rec.controller_route = rec.integration_id._build_webhook_route(method)

    def _compute_is_valid_base_url(self):
        base_url = self.integration_id.get_base_url_config()

        for rec in self:
            rec.is_valid_base_url = (rec.original_base_url == base_url)
