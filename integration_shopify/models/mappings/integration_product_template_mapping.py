# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationProductTemplateMapping(models.Model):
    _inherit = 'integration.product.template.mapping'

    def calculate_import_translations_data(self):
        data = self.external_template_id.prepare_translations_data_in()

        if self.env.context.get('integration_return_action'):
            return self.env['message.wizard'].create_json_and_run(data)

        return data

    def calculate_export_translations_data(self):
        data = self.external_template_id.prepare_translations_data_out()

        if self.env.context.get('integration_return_action'):
            return self.env['message.wizard'].create_json_and_run(data)

        return data
