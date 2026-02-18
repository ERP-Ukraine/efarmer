# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    integration_api_key = fields.Char(
        string='E-Commerce Integration API Key',
        help='API key for the integration.',
    )

    integration_modules_version_info = fields.Text(
        string='E-Commerce Integration Modules Version Information',
        readonly=True,
        help='Complete version information for all integration-related modules.',
    )

    skip_convert_to_webp = fields.Boolean(
        string='Do Not Convert Product Images to WebP Format',
        default=False,
        help='Do not convert product images to webp format.',
    )

    def get_values(self):
        """ Get values for the installed integration. """
        res = super().get_values()

        res.update(
            integration_api_key=self.env['sale.integration'].get_integration_api_key(),
            integration_modules_version_info=self.env['sale.integration'].format_integration_version_info(),
            skip_convert_to_webp=self.env['product.template'].skip_convert_to_webp(),
        )

        return res

    def set_values(self):
        super().set_values()

        self.env['ir.config_parameter'].sudo().set_param(
            'integration.skip_convert_to_webp',
            int(self.skip_convert_to_webp),
        )

    def regenerate_integration_api_key(self):
        self.ensure_one()
        return self.env['sale.integration'].generate_integration_api_key()

    def validate_configuration(self):
        self.ensure_one()
        wizard = self.env['integration.installation.wizard'].create({})
        return wizard.check_odoo_setup_for_integration()

    def open_getting_started_guide(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Getting Started: E-Commerce Connector Made Easy'),
            'res_model': 'integration.configuration.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
