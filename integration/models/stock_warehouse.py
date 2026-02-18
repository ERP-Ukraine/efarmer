# See LICENSE file for full copyright and licensing details.

from odoo import models, _

from ..exceptions import NotMappedToExternal


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def to_external_location(self, integration, raise_error=False):
        if not self:
            # Most likely location for dropshipping orders
            return None

        self.ensure_one()

        location_line = integration.location_line_ids.filtered(lambda x: x.warehouse_id.id == self.id)[:1]

        if not location_line and raise_error:
            raise NotMappedToExternal(_(
                '\nCannot map warehouse "%s" to an external location for integration "%s". '
                'Please ensure the warehouse is mapped correctly in the integration settings.\n\n'
                'Go to: "E-Commerce Integrations → Stores → %s → Inventory tab → Locations".'
            ) % (self.name, integration.name, integration.name),
                model_name=self._name,
                obj_id=self.id,
                integration=integration,
            )

        return location_line.external_location_id.code
