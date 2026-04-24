# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools.misc import groupby

from ..tools import PickingLine, PickingSerializer, SaleTransferSerializer


_logger = logging.getLogger(__name__)


PKG_CONTEXT = dict(
    skip_sms=True,
    skip_expired=True,
    skip_immediate=True,
    skip_backorder=True,
    skip_sanity_check=False,
    skip_dispatch_to_external=True,
)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tracking_exported = fields.Boolean(
        string='Is Tracking Exported?',
        default=False,
        copy=False,
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
        return not self.move_ids.has_kits

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

        if not integration.is_order_tracking_export_enabled:
            return False

        picking = self._filter_pickings()

        if integration.is_carrier_tracking_required():
            picking = picking.filtered('carrier_tracking_ref')

        if not picking:
            return False

        job_kwargs = integration._job_kwargs_export_picking(picking)

        job = integration \
            .with_context(company_id=integration.company_id.id) \
            .with_delay(**job_kwargs) \
            .send_picking(picking)

        self.job_log(job)

        return job

    def _to_export_format(self, integration, multi_serialization=False):
        self.ensure_one()

        serialized_moves = {}
        for move in self.move_ids:
            sale_line = move.sale_line_id

            if not sale_line:
                # Skip move lines without sale order line to avoid errors
                continue

            external_so_line_id = sale_line.to_external(integration)

            if not external_so_line_id:
                # Skip move lines without external order line id to avoid errors
                continue

            related_sale_lines = sale_line._get_related_order_lines()
            qty_demand = int(sum(related_sale_lines.mapped('qty_delivered')))

            qty_done = int(move.quantity)
            is_kit = getattr(move, 'bom_line_id', False)

            if is_kit:
                if multi_serialization:
                    qty_done = qty_demand
                else:
                    # Fulfill all quantities of the kit
                    qty_done = int(sum(related_sale_lines.mapped('product_uom_qty')))

            if external_so_line_id not in serialized_moves:
                serialized_moves[external_so_line_id] = {
                    'qty_done': qty_done,
                    'is_kit': is_kit,
                }
            elif not is_kit:
                # Summarize qty_done for the same external_so_line_id if it is not a kit
                serialized_moves[external_so_line_id]['qty_done'] += qty_done
            else:
                serialized_moves[external_so_line_id]['qty_done'] = max(
                    serialized_moves[external_so_line_id]['qty_done'],
                    qty_done,
                )

        serialized_lines = []
        for external_so_line_id, move_data in serialized_moves.items():
            picking_line = PickingLine(
                external_so_line_id,
                qty_demand,
                move_data['qty_done'],
                move_data['is_kit'],
                multi_serialization=multi_serialization,
            )

            serialized_lines.append(picking_line)

        carrier_code = ''
        if self.carrier_id:
            carrier_code = self.carrier_id.get_external_carrier_code(integration)

        _args = {
            'erp_id': self.id,
            'name': self.name,
            'carrier': self.carrier_id.name or '',
            'carrier_code': carrier_code or self.carrier_id.name or '',
            'is_backorder': bool(self.backorder_id),
            'is_dropship': getattr(self, 'is_dropship', False),
            'tracking': self.carrier_tracking_ref or '',
        }
        return PickingSerializer(data=_args, lines=serialized_lines)

    def to_export_format(self, integration):
        picking_serializer = self._to_export_format(integration)
        data = picking_serializer.serialize()

        external_location_id = self.location_id.warehouse_id.to_external_location(integration)
        data['external_location_id'] = external_location_id

        return data

    def to_export_format_multi(self, integration):
        tracking_data_list = list()

        for rec in self:
            picking_serializer = rec._to_export_format(integration, multi_serialization=True)
            tracking_data_list.append(picking_serializer)

        transfer = SaleTransferSerializer(tracking_data_list).squash()
        tracking_data = transfer.dump()

        for data in tracking_data:
            picking = self.filtered(lambda x: x.id == data['picking_id'])
            external_location_id = picking.location_id.warehouse_id.to_external_location(integration)

            data['external_location_id'] = external_location_id

        return tracking_data

    def _auto_validate_picking(self):
        """Set quantities automatically and validate the pickings."""
        for picking in self._filter_pickings_to_handle():
            for move in picking.move_ids.filtered(
                lambda m: m.state not in ['done', 'cancel']
            ):
                if move._move_qty_lack():
                    for move_line in move.move_line_ids:
                        move_line.quantity = move_line.quantity_product_uom

            try:
                # Let's rely on the `_sanity_check` (skip_sanity_check=False)
                # standard method to get verbose error
                res = picking.with_context(**PKG_CONTEXT).button_validate()

                # Picking validation is not guaranteed to complete automatically:
                # it may raise a UserError or return a UI action requiring manual input.
                # Such cases are treated as non-auto-validatable.
                if isinstance(res, dict) and res.get('type') == 'ir.actions.act_window':
                    _logger.info(
                        'Picking [%s] requires manual validation.',
                        picking.display_name,
                    )

                    return False, _(
                        '[%s] requires manual validation.\n'
                        'Validation result: %s'
                    ) % (picking.display_name, res)

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
        """
        Run integration hooks for pickings.
        This method is responsible for handling the integration logic
        when pickings are validated or canceled. It checks if the order
        is shipped and performs the necessary actions based on the integration type.
        """
        # Access orders as sudo to avoid issues with missed access rights
        # Person who works with pickings can have no access to sales orders
        for order, picking_list in groupby(self.sudo(), key=lambda x: x.sale_id):
            integration = order.integration_id
            if not integration:
                # If order is not from integration - do nothing
                continue

            # Option 1: Order is fully shipped; perform full delivery validation
            if order.check_is_order_shipped():
                order._integration_shipped_order_hook()
                order.order_export_tracking()
                continue

            # Option 2: Order is not fully shipped; perform partial delivery validation for
            # Shopify, Magento2 or do nothing for other integrations
            if integration.is_integration_shopify or integration.is_integration_magento_two:
                for rec in picking_list:
                    rec.integration_send_picking()

                continue

    def _filter_pickings(self):
        return self.filtered(
            lambda x: x.state == 'done' and not x.tracking_exported
            and (
                x.picking_type_id.code == 'outgoing'
                or getattr(x, 'is_dropship', False)
            )
        )

    def _filter_pickings_to_handle(self):
        return self.filtered(lambda x: x.state in ('confirmed', 'assigned'))

    def _validate_external_fulfillment(self, fulfillment):
        # 1. Filter actual moves
        actual_move_ids = self.move_ids.browse()
        for line in fulfillment.line_ids:
            actual_move_ids |= self._get_moves_by_external_line(line.external_str_id)

        # 2. Skip the rest of the moves
        for move in (self.move_ids - actual_move_ids):
            for move_line in move.move_line_ids:
                move_line.quantity = 0

        # 3. Handle fulfillment lines
        MrpBom = self.env['mrp.bom']

        for line in fulfillment.line_ids:
            moves = self._get_moves_by_external_line(line.external_str_id)

            sale_line = moves[:1].sale_line_id
            product = sale_line.product_id

            bom_kit = MrpBom._bom_find(product, bom_type='phantom')[product]
            fulfill_quantity = int(line.quantity)

            if bom_kit:
                __, bom_sub_lines = bom_kit.explode(product, fulfill_quantity, picking_type=self.picking_type_id)

                qty_dict = {line.product_id.id: int(dct['qty']) for (line, dct) in bom_sub_lines}
            else:
                qty_dict = {product.id: fulfill_quantity}

            for move in moves:
                move_product_id = move.product_id.id
                fulfill_quantity = qty_dict.get(move_product_id, 0)

                for move_line in move.move_line_ids:
                    if not fulfill_quantity:
                        continue

                    qty_demand = move_line.quantity_product_uom

                    if qty_demand <= fulfill_quantity:
                        value = qty_demand
                        fulfill_quantity -= value
                    else:
                        value = fulfill_quantity

                    move_line.quantity = value
                    qty_dict[move_product_id] = fulfill_quantity

        if fulfillment.tracking_number:
            self.carrier_tracking_ref = fulfillment.tracking_number

        if fulfillment.tracking_company:
            carrier = self.env['delivery.carrier']._get_carrier_by_external_name(
                self.sale_id.integration_id,
                fulfillment.tracking_company,
            )
            self.carrier_id = carrier.id

        return self.with_context(**PKG_CONTEXT).button_validate()

    def _check_for_fulfill(self, lines: models.Model):  # lines: external.order.fulfillment.line
        return all(self._check_qty_availability(x.external_str_id, x.quantity) for x in lines)

    def _check_qty_availability(self, line_id: str, qty: int):
        moves = self._get_moves_by_external_line(line_id)
        order_line = moves.mapped('sale_line_id')
        return any((x.qty_to_deliver >= qty) for x in order_line)

    def _get_moves_by_external_line(self, line_id: str):
        moves = self.move_ids.filtered(
            lambda x: x.state not in ('done', 'cancel')
            and x.integration_external_id == line_id
            and x._has_enough_qty()
        )
        return moves
