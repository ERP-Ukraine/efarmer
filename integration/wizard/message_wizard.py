# See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.tools import unsafe_eval


class MessageWizard(models.TransientModel):
    _name = 'message.wizard'
    _description = 'Show Message'

    message = fields.Text(
        string='Message',
        required=True,
    )
    message_html = fields.Html(
        string='HTML Message',
    )

    def download_html(self):
        vals = {
            'type': 'ir.actions.act_url',
            'name': 'Download Html',
            'target': 'self',
            'url': '/integration/messagewizard/export?res_id=%s' % self.id,
        }
        return vals

    def action_close(self):
        return {
            'type': 'ir.actions.act_window_close',
        }

    def run_wizard(self, view_name):
        return {
            'type': 'ir.actions.act_window',
            'name': 'INFO',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(f'integration.{view_name}').id,
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
            'view_mode': 'tree',
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
