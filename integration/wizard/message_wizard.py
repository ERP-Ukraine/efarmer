# See LICENSE file for full copyright and licensing details.

import base64

from odoo import api, models, fields

from ..tools import safe_json_dumps

# eval to compile generated string python code into binary code, used in `_compile`
unsafe_eval = eval


class MessageWizard(models.TransientModel):
    _name = 'message.wizard'
    _inherit = 'export.file.mixin'
    _description = 'Show Message'

    message = fields.Text(
        string='Message',
    )

    def download_pdf(self):
        pdf_bytes = self._convert_html_to_pdf_bytes(self.export_html or self.message)
        self.export_pdf = base64.b64encode(pdf_bytes)
        return super().download_pdf()

    def action_close(self):
        return {
            'type': 'ir.actions.act_window_close',
        }

    @api.model
    def create_and_run(self, data: str):
        wizard = self.create({
            'message': data,
        })
        return wizard.run_wizard('integration_message_wizard_form')

    @api.model
    def create_json_and_run(self, data: dict):
        wizard = self.create({
            'export_json': safe_json_dumps(data, indent=4),
        })
        return wizard.run_wizard('integration_message_wizard_json_form')

    @api.model
    def create_html_and_run(self, data: str):
        wizard = self.create({
            'export_html': data,
        })
        return wizard.run_wizard('integration_message_wizard_html_form')

    def run_wizard(self, view_name: str):
        view_name_ = view_name if '.' in view_name else f'integration.{view_name}'

        return {
            'type': 'ir.actions.act_window',
            'name': 'INFO',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(view_name_).id,
            'target': 'new',
        }

    def open_mapping(self):
        """Specific method for the Integration Product Template Mapping model only."""
        return self._open_mapping()

    def _open_mapping(self):
        view = self.env.ref(
            'integration.integration_product_template_mapping_view_tree',
        )
        params = {
            'type': 'ir.actions.act_window',
            'name': 'INFO',
            'res_model': 'integration.product.template.mapping',
            'view_mode': 'list',
            'view_id': view.id,
            'target': 'self',
        }

        try:
            record_ids = unsafe_eval(self.message)
        except Exception:
            record_ids = list()

        if record_ids:
            params['domain'] = [('id', 'in', record_ids)]

        return params
