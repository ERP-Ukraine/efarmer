# See LICENSE file for full copyright and licensing details.

import json

from odoo import models


class SaleIntegrationInputFile(models.Model):
    _inherit = 'sale.integration.input.file'

    def fetch_full_order(self):
        self.ensure_one()

        if not self.si_id.is_integration_shopify:
            return False

        order_data = self.si_id.adapter.receive_order(self.name)

        if not order_data:
            return self.env['message.wizard'].create_and_run(
                'Order with ID=%s not found in the external system.' % self.name,
            )

        vals = {
            'raw_data': json.dumps(order_data['data'], indent=4),
            'update_required': False,
        }

        return self.write(vals)

    def _get_external_reference(self):
        if self.si_id.is_integration_shopify:
            return self._get_external_reference_root('name')
        return super(SaleIntegrationInputFile, self)._get_external_reference()
