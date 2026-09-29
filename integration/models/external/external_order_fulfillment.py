# See LICENSE file for full copyright and licensing details.
from copy import deepcopy

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError


class ExternalOrderFulfillment(models.Model):
    _name = 'external.order.fulfillment'
    _inherit = 'external.order.resource'
    _description = 'External Order Fulfillment Information'

    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('cancelled', 'Cancelled'),
            ('error', 'Error'),
            ('failure', 'Failure'),
        ],
        string='Shipment Status',
        help='Fulfillment status as reported by the e-commerce platform',
    )

    external_location_id = fields.Char(
        string='Warehouse Location ID',
        help='External identifier for the warehouse or fulfillment location',
    )
    tracking_company = fields.Char(
        string='Shipping Carrier',
        help='Name of the shipping company or carrier (e.g., FedEx, UPS, DHL)',
    )
    tracking_number = fields.Char(
        string='Tracking Number',
        help='Shipping tracking number for package delivery',
    )
    line_ids = fields.One2many(
        comodel_name='external.order.fulfillment.line',
        inverse_name='fulfillment_id',
        string='Fulfilled Items',
        help='List of order items included in this fulfillment',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Validated Picking',
        help='The Odoo stock.picking validated by this fulfillment. '
             'Populated when fulfillment processing succeeds. Used by return '
             'processing to identify the source picking for partition logic. '
             'Note: if one fulfillment spans multiple pickings (backorders), '
             'this reflects the first picking only (pre-existing limitation).',
    )
    do_cancel_external = fields.Boolean(
        string='Cancel in External System',
        help='When checked, this fulfillment will be cancelled in the external e-commerce system',
    )

    def _validate(self):
        """
        Process external fulfillment data in Odoo.

        Performs delivery validation by matching fulfillment items with pending pickings
        and updating the delivery status.

        Returns:
            tuple: (success, picking_ids)
        """
        self.internal_info = False

        if self.is_done:
            return True, []

        if not self.is_ecommerce_ok:
            self.internal_info = _('Fulfillment skipped - external status does not allow processing')
            self.mark_skipped()
            return False, []

        pickings = self._get_pickings()
        if not pickings:
            self.internal_info = _('No pending deliveries found for this order')
            # If the outgoing picking was already validated before this fulfillment record was
            # processed (e.g. manual user validation), record it on picking_id so return
            # processing can locate it.
            already_validated = self._resolve_already_validated_picking()
            if already_validated:
                self.picking_id = already_validated.id
            self.mark_done()
            return True, []

        picking = pickings.filtered(lambda x: x._check_for_fulfill(self.line_ids))[:1]
        # TODO: Handle cases where fulfillment matches multiple pickings
        if not picking:
            self.internal_info = _('No matching delivery found for the fulfilled items')
            return False, []

        try:
            result = picking._validate_external_fulfillment(self)
        except (UserError, ValidationError) as ex:
            self.internal_info = f'Delivery validation failed: {ex.args[0]}'
            self.mark_failed()
            return False, []

        picking.mark_integration_sent()
        # Cache the validated picking so return processing can identify which outgoing picking
        # each return line should be created against. Limitation: if one fulfillment spans
        # multiple pickings (backorders), only the first is stored — see the TODO above.
        self.picking_id = picking.id
        self.mark_done()

        return result, picking.ids

    def _compute_is_ecommerce_ok(self):
        """Check if the fulfillment status allows processing in Odoo"""
        for rec in self:
            rec.is_ecommerce_ok = (rec.state == 'success')

    def cancel_in_ecommerce_system(self):
        """
        Cancel this fulfillment in the external e-commerce system.
        """
        self.ensure_one()

        result = self.integration_id.adapter.cancel_fulfillment(self.external_str_id)

        if result:
            self.state = 'cancelled'

        return result

    def _resolve_already_validated_picking(self):
        """Find the done outgoing picking corresponding to this fulfillment.

        Used in the `no pending deliveries` branch of _validate() — covers
        the case where the outgoing picking was already validated before
        fulfillment processing ran. Returns an empty recordset if no
        unambiguous match can be made; the caller should leave picking_id
        empty and let return processing fall back to legacy resolution.
        """
        self.ensure_one()

        order = self.erp_order_id
        done_outgoing = order.picking_ids.filtered(
            lambda p: p.state == 'done'
            and p.picking_type_id.code == 'outgoing'
        )

        if order.is_available_multi_stock_for_so:
            warehouse = self.integration_id._get_wh_from_external_location(
                self.external_location_id
            )
            if warehouse:
                done_outgoing = done_outgoing.filtered(
                    lambda p: p.location_id.warehouse_id.id == warehouse.id
                )

        # Try to identify a specific picking via line external IDs. This disambiguates when an
        # order has multiple done outgoing pickings (e.g. backorders, multi-shipment fulfillments).
        line_ext_ids = [
            x for x in self.line_ids.mapped('external_str_id') if x
        ]
        if line_ext_ids:
            matched = done_outgoing.filtered(
                lambda p: any(
                    m.integration_external_id in line_ext_ids
                    for m in p.move_ids
                )
            )
            if len(matched) == 1:
                return matched

        # Fallback: unique done outgoing picking on the order.
        if len(done_outgoing) == 1:
            return done_outgoing

        return done_outgoing.browse()

    def action_cancel_in_ecommerce_system(self):
        """Button entry point for `cancel_in_ecommerce_system`: cancel and show a confirmation toast."""
        result = self.cancel_in_ecommerce_system()
        title = _('Cancel Fulfillment')

        if result:
            return self.display_integration_notification(
                _('The fulfillment has been cancelled in the e-commerce system.'), title=title,
            )

        return self.display_integration_notification(
            _('Unable to cancel the fulfillment in the e-commerce system.'), title=title, ttype='warning',
        )

    def _get_pickings(self):
        """
        Get relevant delivery pickings for this fulfillment.

        Filters pickings based on warehouse location if multi-warehouse is enabled.

        Returns:
            recordset: Filtered delivery pickings
        """
        pickings = self.erp_order_id._get_pickings_to_handle()

        if self.erp_order_id.is_available_multi_stock_for_so:
            warehouse = self.integration_id._get_wh_from_external_location(self.external_location_id)

            if warehouse:
                pickings = pickings.filtered(lambda x: x.location_id.warehouse_id.id == warehouse.id)

        return pickings

    def _prepare_vals_from_external(self, data: dict) -> dict:
        """
        Prepare values for creating/updating fulfillment records from external data.

        Args:
            data (dict): Raw external fulfillment data

        Returns:
            dict: Prepared values for Odoo record
        """
        vals = deepcopy(data)

        # Populate state from external_status if not explicitly set
        if 'state' not in vals and 'external_status' in vals:
            vals['state'] = vals['external_status']

        lines = vals.pop('lines', [])
        # Clear existing lines and add new ones
        vals['line_ids'] = [(5,)] + [(0, 0, x) for x in lines]

        return vals
