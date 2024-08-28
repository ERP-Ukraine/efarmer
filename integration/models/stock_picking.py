# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

from ..tools import PickingLine, PickingSerializer, SaleTransferSerializer


_logger = logging.getLogger(__name__)


PKG_CONTEXT = dict(
    skip_sms=True,
    skip_expired=True,
    skip_immediate=True,
    skip_backorder=True,
    skip_dispatch_to_external=True,
)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tracking_exported = fields.Boolean(
        string='Is Tracking Exported?',
        default=False,
        help='This flag allows us to define if tracking code for this picking was exported '
             'for external integration. It helps to avoid sending same tracking number twice. '
             'Basically we need this flag, cause different carriers have different type of '
             'integration. And sometimes tracking reference is added to stock picking after it '
             'is validated and not at the same moment.',
    )

    def write(self, vals):
        # if someone add `carrier_tracking_ref` after picking validation
        picking_done_ids = self.filtered(
            lambda x: x.state == 'done' and not x.carrier_tracking_ref
        )
        res = super(StockPicking, self).write(vals)

        picking_done_update_ids = picking_done_ids.filtered(
            lambda x: x.state == 'done' and x.carrier_tracking_ref
        )
        for order in picking_done_update_ids.mapped('sale_id'):
            # It seems it may trigger the parallel picking export during picking validation
            if order.check_is_order_shipped():
                order.order_export_tracking()

        return res

    @property
    def no_kits(self):
        """Inverse property due to there is `has_kits` compute field in the mrp module"""
        self.ensure_one()
        return not self.move_lines.has_kits

    def mark_integration_sent(self):
        self.write({
            'tracking_exported': True,
        })

    def integration_send_picking(self):
        self.ensure_one()

        if self.env.context.get('skip_dispatch_to_external'):
            return False

        integration = self.sale_id.integration_id
        if not integration:
            return False

        if not integration.job_enabled('export_tracking'):
            return False

        picking = self._filter_pickings()

        if integration.is_carrier_tracking_required():
            picking = picking.filtered('carrier_tracking_ref')

        if not picking:
            return False

        kwargs = {
            'identity_key': f'integration_send_picking-{integration.id}-{self.id}',
            'description': f'{integration.name}: Send Picking [{self.name}] ({self.id})',
        }
        integration = integration.with_context(company_id=integration.company_id.id)

        job = integration.with_delay(**kwargs).send_picking(picking)
        self.job_log(job)

        return job

    def _to_export_format(self, integration):
        self.ensure_one()

        serialized_lines = list()
        for move in self.move_lines:
            sale_line = move.sale_line_id

            if not sale_line:
                # Skip move lines without sale order line to avoid errors
                continue

            external_so_line_id = sale_line.to_external(integration)
            relatives = sale_line._get_relatives()
            qty_demand = int(sum(relatives.mapped('qty_delivered')))

            if external_so_line_id and qty_demand:
                qty_done = int(move.quantity_done)
                is_kit = False

                if getattr(move, 'bom_line_id', False):
                    is_kit = True
                    qty_done = qty_demand

                picking_line = PickingLine(external_so_line_id, qty_demand, qty_done, is_kit)
                serialized_lines.append(picking_line)

        carrier = str()
        if self.carrier_id:
            carrier = self.carrier_id.get_external_carrier_code(integration)
            if not carrier:
                carrier = self.carrier_id.name

        _args = (
            {
                'erp_id': self.id,
                'name': self.name,
                'carrier': carrier,
                'is_backorder': bool(self.backorder_id),
                'is_dropship': getattr(self, 'is_dropship', False),
                'tracking': self.carrier_tracking_ref or '',
            },
            serialized_lines,
        )
        return PickingSerializer(*_args)

    def to_export_format(self, integration):
        picking_serializer = self._to_export_format(integration)
        if picking_serializer.has_components():
            return False

        data = picking_serializer.serialize()

        external_location_id = False
        if self.sale_id.is_available_multi_stock_for_so:
            external_location_id = self.location_id.warehouse_id\
                .to_external_location(integration, raise_error=True)

        data['external_location_id'] = external_location_id
        return data

    def to_export_format_multi(self, integration):
        tracking_data_list = list()

        for rec in self:
            picking_serializer = rec._to_export_format(integration)
            tracking_data_list.append(picking_serializer)

        transfer = SaleTransferSerializer(tracking_data_list).squash()
        tracking_data = transfer.dump()

        for data in tracking_data:
            external_location_id = False
            if self.sale_id.is_available_multi_stock_for_so:
                picking = self.filtered(lambda x: x.id == data['picking_id'])

                external_location_id = picking.location_id.warehouse_id\
                    .to_external_location(integration, raise_error=True)

            data['external_location_id'] = external_location_id

        return tracking_data

    def _auto_validate_picking(self):
        """Set quantities automatically and validate the pickings."""
        for picking in self._filter_pickings_to_handle():
            for move in picking.move_lines.filtered(
                lambda m: m.state not in ['done', 'cancel']
            ):
                if not move.reserved_availability:
                    return False, _('Not enough inventory to validate picking %s') \
                        % picking.display_name

                if move._move_qty_lack():
                    for move_line in move.move_line_ids:
                        move_line.qty_done = move_line.product_uom_qty

            try:
                # Let's rely on the `_sanity_check` (skip_sanity_check=False)
                # standard method to get verbose error
                picking.with_context(**PKG_CONTEXT).button_validate()
            except UserError as ex:
                return False, f'[{picking.display_name}]: {ex.args[0]}'

            # Let's check the presence of pickings for validation,
            # as there might be a back order created.
            pickings = self.mapped('sale_id').picking_ids._filter_pickings_to_handle()
            if pickings:
                return pickings._auto_validate_picking()

        if any(self.filtered(lambda x: x.state == 'waiting')):
            message = _('%s is not ready to be validated. Waiting another operation.') % ', '.join(
                self.filtered(lambda x: x.state == 'waiting').mapped('display_name'),
            )
            return False, message

        return True, _('[%s] validated pickings successfully.') % ', '.join(
            self.mapped('display_name')
        )

    def button_validate(self):
        """
        Override button_validate method to called method, that check order is shipped or not.
        """
        res = super(StockPicking, self).button_validate()

        if res is not True:
            return res

        self._run_integration_picking_hooks()

        return res

    def action_cancel(self):
        res = super(StockPicking, self).action_cancel()

        if res is not True:
            return res

        self._run_integration_picking_hooks()

        return res

    def _run_integration_picking_hooks(self):
        # Access orders as sudo to avoid issues with missed access rights
        # Person who works with pickings can have no access to sales orders
        orders = self.sudo().mapped('sale_id')

        # If order is not from integration - do nothing
        orders = orders.filtered('integration_id')

        for order in orders:
            if not order.check_is_order_shipped():
                continue

            order._integration_shipped_order_hook()
            order.order_export_tracking()

    def _filter_pickings(self):
        return self.filtered(
            lambda x: x.state == 'done' and not x.tracking_exported
            and (
                x.picking_type_id.id == x.picking_type_id.warehouse_id.out_type_id.id
                or getattr(x, 'is_dropship', False)
            )
        )

    def _filter_pickings_to_handle(self):
        return self.filtered(lambda x: x.state in ('confirmed', 'assigned'))

    def _validate_external_fulfillment(self, fulfillment):
        # 1. Filter actual moves
        actual_move_ids = self.move_lines.browse()
        for line in fulfillment.line_ids:
            actual_move_ids |= self._get_moves_by_external_line(line.external_str_id)

        # 2. Skip the rest of the moves
        for move in (self.move_lines - actual_move_ids):
            for move_line in move.move_line_ids:
                move_line.qty_done = 0

        # 3. Handle fulfillment lines
        for line in fulfillment.line_ids:
            moves = self._get_moves_by_external_line(line.external_str_id)

            fulfill_quantity = line.quantity
            for move in moves:
                for move_line in move.move_line_ids:
                    if not fulfill_quantity:
                        continue

                    qty_demand = move_line.product_qty

                    if qty_demand <= fulfill_quantity:
                        value = qty_demand
                        fulfill_quantity -= value
                    else:
                        value = fulfill_quantity

                    move_line.qty_done = value

        if fulfillment.tracking_number:
            self.carrier_tracking_ref = fulfillment.tracking_number

        if fulfillment.tracking_company:
            carrier = self.env['delivery.carrier'].search([
                ('shopify_code', '=', fulfillment.tracking_company),
            ], limit=1)
            self.carrier_id = carrier.id

        return self.with_context(**PKG_CONTEXT).button_validate()

    def _check_for_fulfill(self, lines):
        return all(self._check_qty_possibility(x.external_str_id, x.quantity) for x in lines)

    def _check_qty_possibility(self, line_id, qty):
        moves = self._get_moves_by_external_line(line_id)
        order_line = moves.mapped('sale_line_id')
        return any((x.qty_to_deliver >= qty) for x in order_line)

    def _get_moves_by_external_line(self, line_id):
        moves = self.move_lines.filtered(
            lambda x: x.state not in ('done', 'cancel')
            and x.integration_external_id == line_id
            and x._has_enough_qty()
        )

        moves_kits = moves.filtered(lambda x: x.has_kits)  # TODO
        if moves_kits and not (moves - moves_kits):
            _logger.warning(
                'Integration: Partial picking validation for product with BOM components: %s',
                moves_kits.mapped('name'),
            )

        return (moves - moves_kits) or moves
