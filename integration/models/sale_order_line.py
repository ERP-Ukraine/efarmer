# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'integration.model.mixin']

    integration_external_id = fields.Char(
        string='Intgration External ID',
    )

    def to_external(self, integration):
        self.ensure_one()
        assert self.order_id.integration_id == integration
        return self.integration_external_id

    def _is_deliverable_product(self):
        """
        Returns True if the line includes the deliverable product
        :returns: boolean
        """
        self.ensure_one()

        if not self.product_id or self.product_id.type == 'service' or self._is_delivery():
            return False
        return True
