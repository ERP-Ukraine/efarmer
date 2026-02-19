# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'integration.model.mixin']

    integration_external_id = fields.Char(
        string='Integration External ID',
    )

    external_location_id = fields.Char(
        string='External Location ID',
    )

    def to_external(self, integration):
        self.ensure_one()
        assert self.order_id.integration_id == integration
        return self.integration_external_id

    def _get_related_order_lines(self):
        """
        Get the all Odoo order-lines belonging to the same external-order-line
        which was automatically splitted by the location during order parsing.
        """
        external_code = self.integration_external_id
        return self.order_id.order_line.filtered(
            lambda x: x.integration_external_id == external_code
        )

    def _is_deliverable_product(self):
        """
        Returns True if the line includes the deliverable product
        :returns: boolean
        """
        self.ensure_one()

        if not self.product_id or self.product_id.type == 'service' or self._is_delivery():
            return False
        return True

    def _process_gift_message(self, message):
        self.ensure_one()

        message_to_write = _('\nMessage to write: %s') % message
        self.name += message_to_write

        order = self.order_id
        note_field = order.integration_id.so_delivery_note_field

        if note_field and note_field.name:
            order_notes = getattr(order, note_field.name) or ''
            delivery_notes = order_notes + message_to_write

            setattr(order, note_field.name, delivery_notes)
