# See LICENSE file for full copyright and licensing details.
from copy import deepcopy

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError


class ExternalOrderFulfillment(models.Model):
    _name = 'external.order.fulfillment'
    _inherit = 'external.order.resource'
    _description = 'External Order Fulfillment Information'

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
        self.mark_done()

        return result, picking.ids

    def _compute_is_ecommerce_ok(self):
        """Check if the fulfillment status allows processing in Odoo"""
        for rec in self:
            rec.is_ecommerce_ok = (rec.external_status == 'success')

    def cancel_in_ecommerce_system(self):
        """
        Cancel this fulfillment in the external e-commerce system.

        Returns:
            dict: Result from the external system API call
        """
        self.ensure_one()

        result = self.integration_id.adapter.cancel_fulfillment(self.external_str_id)

        if result:
            self.external_status = 'cancelled'

        return result

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

        lines = vals.pop('lines', [])
        # Clear existing lines and add new ones
        vals['line_ids'] = [(5,)] + [(0, 0, x) for x in lines]

        return vals
