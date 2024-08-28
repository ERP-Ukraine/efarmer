# See LICENSE file for full copyright and licensing details.

from odoo import models, _
from odoo.exceptions import UserError

from ..exceptions import NotMappedToExternal


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def to_external_location(self, integration, raise_error=False):
        self.ensure_one()
        location_line = integration.location_line_ids.filtered(lambda x: x.warehouse_id.id == self.id)  # TODO ???

        if not location_line and raise_error:
            raise NotMappedToExternal(
                _('Can\'t map odoo value to external code'),
                self._name,
                self.id,
                integration,
            )

        if len(location_line) > 1:
            raise UserError(
                _('%s: %s (%s) - multiple mapping found.') % (integration.name, self, self.name)
            )

        return location_line.external_location_id.code
