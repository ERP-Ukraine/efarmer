# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ExternalOrderFulfillment(models.Model):
    _inherit = 'external.order.fulfillment'

    shopify_fulfillment_orders = fields.Json(
        string='Shopify Fulfillment Orders',
        help='Ids of the Shopify fulfillment orders this fulfillment closed. A collection of a pickup is matched by '
             'them to the delivery that marked the goods ready.',
    )

    def _validate(self):
        # A pickup picking only marks the goods ready, so Shopify has no fulfillment for them until the merchant
        # records the collection. That fulfillment closes the fulfillment orders the picking marked ready, and it
        # is the picking's own goods: Shopify prepares a fulfillment order whole. Matched to a pending delivery
        # instead, it would validate a backorder of goods still on the shelf.
        if not self.is_done and self.is_ecommerce_ok:
            picking = self._get_prepared_picking()

            if picking:
                self.internal_info = _('The fulfilled items were already delivered in Odoo')
                self.picking_id = picking.id
                self.mark_done()
                return True, []

        return super()._validate()

    def _get_prepared_picking(self):
        """The done picking that marked the fulfillment orders of this fulfillment ready for pickup.

        Every fulfillment order of the fulfillment must have been marked ready by a done picking of the order. A
        collection that also takes goods Odoo has not delivered goes the usual way, so those goods are not lost.

        Returns:
            stock.picking: the first such picking, or an empty recordset
        """
        order_ids = self.shopify_fulfillment_orders or []
        pickings = self.erp_order_id.picking_ids.filtered(lambda x: x.is_done and x.shopify_ready_fulfillment_orders)
        ready = {y for x in pickings for y in x.shopify_ready_fulfillment_orders}

        if not order_ids or not set(order_ids) <= ready:
            return self.env['stock.picking']

        return pickings.filtered(lambda x: set(order_ids) & set(x.shopify_ready_fulfillment_orders)).sorted('id')[:1]
