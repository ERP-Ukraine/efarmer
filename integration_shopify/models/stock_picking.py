# See LICENSE file for full copyright and licensing details.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @property
    def carrier_tracking_url_prop(self):
        self.ensure_one()
        return self.carrier_id.integration_send_tracking_url and self.carrier_tracking_url or False

    @property
    def is_done(self):
        self.ensure_one()
        return self.state == 'done'

    def to_export_format(self, integration: 'models.Model'):
        result = super().to_export_format(integration)

        if integration.is_integration_shopify:
            result['carrier_tracking_url'] = self.carrier_tracking_url_prop

        return result

    def to_export_format_multi(self, integration):
        result = super().to_export_format_multi(integration)

        if integration.is_integration_shopify:

            for data, picking in zip(result, self):
                data['carrier_tracking_url'] = picking.carrier_tracking_url_prop

        return result

    def button_validate(self):
        """
        Override button_validate method to called method, that check order is shipped or not.
        """
        res = super(StockPicking, self).button_validate()

        for record in self:
            if record.is_done:
                record._run_integration_picking_hooks()

        return res
