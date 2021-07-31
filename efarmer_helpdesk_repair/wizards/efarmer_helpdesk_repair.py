from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class EfarmerHelpdeskRepair(models.TransientModel):
    _name = 'efarmer.helpdesk.repair'
    _description = 'Helpdesk Repair/Replace Wizard'

    def _get_default_weeks_to_repair(self):
        return 3

    # It's supposed that the field value will be set up from the context.
    ticket_id = fields.Many2one('helpdesk.ticket', 'Helpdesk Ticket', readonly=True, required=True)

    product_id = fields.Many2one('product.product', 'Product', related='ticket_id.product_id', readonly=True, required=True)
    product_tracking = fields.Selection(related='ticket_id.product_id.tracking')
    factory_id = fields.Many2one('stock.warehouse', 'Factory', related='ticket_id.factory_id', readonly=True, required=True)
    lot_id = fields.Many2one('stock.production.lot', 'Lot Number', related='ticket_id.lot_id', readonly=True)

    operation_type = fields.Selection(
        string='Operation Type',
        selection=[
            ('repair', 'Repair'),
            ('repair_replace', 'Repair-Replace'),
            ('repair_replace_return', 'Repair-Replace-Return'),
        ],
        default='repair',
        required=True,
    )

    return_warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Return Path',
        domain='[("id", "!=", factory_id)]',
    )

    return_date = fields.Date('Return Date', default=fields.Date.today, required=True)
    weeks_to_repair = fields.Integer('Repair Time', default=_get_default_weeks_to_repair, required=True)

    replacement_product_id = fields.Many2one('product.product', 'Replacement Product')
    used_warehouse_id = fields.Many2one('stock.warehouse', 'Used Warehouse')
    stock_warehouse_id = fields.Many2one('stock.warehouse', 'Stock Warehouse')

    customer_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Customer',
        default=lambda x: x.env.ref('stock.stock_location_customers'),
        readonly=True,
    )

    should_go_through_transit_warehouse = fields.Boolean('Go through transit warehouse', default=False)

    @api.onchange('used_warehouse_id')
    def _onchange_used_warehouse_id(self):
        replacement_product_domain = []
        if self.used_warehouse_id:
            location = self.used_warehouse_id.lot_stock_id
            all_products = self.env['stock.quant'].search([('location_id', 'child_of', location.id)]).mapped('product_id')
            avail_products = all_products.with_context(location=location.id).filtered(lambda x: x.qty_available > 0)
            replacement_product_domain.append(('id', 'in', avail_products.ids))

        return {
            'domain': {'replacement_product_id': replacement_product_domain},
        }

    def action_run(self):
        self.ensure_one()

        # Prepare fields ...

        date_of_delivering_to_factory = self.return_date
        date_of_repair_completion = self.return_date + timedelta(weeks=max(self.weeks_to_repair, 0))

        factory_location = self.factory_id.lot_stock_id
        return_location = self.return_warehouse_id.lot_stock_id

        incoming_picking_type = self.factory_id.in_type_id
        outgoing_picking_type = self.factory_id.out_type_id
        internal_picking_type = self.factory_id.int_type_id

        return_internal_picking_type = self.return_warehouse_id.int_type_id

        used_location = self.used_warehouse_id.lot_stock_id
        stock_location = self.stock_warehouse_id.lot_stock_id

        if not all((
            # These picking types below are necassary anyway.
            incoming_picking_type and outgoing_picking_type,
            # The internal picking type is needed for the repair/replace operation.
            self.operation_type != 'repair_replace' or internal_picking_type,
            # The return internal picking type is needed only when we do transit moves.
            (not self.should_go_through_transit_warehouse and self.operation_type != 'repair_replace_return') or return_internal_picking_type,
        )):
            raise UserError('At first you should set up picking types on the warehouses.')

        # Create pickings ...

        if self.operation_type == 'repair':

            if self.should_go_through_transit_warehouse:
                # customer > return > factory
                picking = self._create_picking(incoming_picking_type, self.customer_location_id, return_location, move_date=date_of_delivering_to_factory)
                self._create_picking(return_internal_picking_type, return_location, factory_location, prev_move=picking and picking.move_lines, move_date=date_of_delivering_to_factory)
                # factory > return > customer
                picking = self._create_picking(return_internal_picking_type, factory_location, return_location, move_date=date_of_repair_completion)
                self._create_picking(outgoing_picking_type, return_location, self.customer_location_id, prev_move=picking and picking.move_lines, move_date=date_of_repair_completion)
            else:
                # customer > factory
                self._create_picking(incoming_picking_type, self.customer_location_id, factory_location, move_date=date_of_delivering_to_factory)
                # factory > customer
                self._create_picking(outgoing_picking_type, factory_location, self.customer_location_id, move_date=date_of_repair_completion)

        elif self.operation_type == 'repair_replace':

            if self.should_go_through_transit_warehouse:
                # customer > return > factory
                picking = self._create_picking(incoming_picking_type, self.customer_location_id, return_location, move_date=date_of_delivering_to_factory)
                self._create_picking(return_internal_picking_type, return_location, factory_location, prev_move=picking and picking.move_lines, move_date=date_of_delivering_to_factory)
                # used > return > customer
                picking = self._create_picking(return_internal_picking_type, used_location, return_location)
                self._create_picking(outgoing_picking_type, return_location, self.customer_location_id, prev_move=picking and picking.move_lines)
                # factory > return > stock
                picking = self._create_picking(internal_picking_type, factory_location, return_location, move_date=date_of_repair_completion)
                self._create_picking(internal_picking_type, return_location, stock_location, prev_move=picking and picking.move_lines, move_date=date_of_repair_completion)
            else:
                # customer > factory
                self._create_picking(incoming_picking_type, self.customer_location_id, factory_location, move_date=date_of_delivering_to_factory)
                # used > customer
                self._create_picking(outgoing_picking_type, used_location, self.customer_location_id)
                # factory > stock
                self._create_picking(internal_picking_type, factory_location, stock_location, move_date=date_of_repair_completion)

        elif self.operation_type == 'repair_replace_return':

            if self.should_go_through_transit_warehouse:
                # customer > return > factory
                picking = self._create_picking(incoming_picking_type, self.customer_location_id, return_location, move_date=date_of_delivering_to_factory)
                self._create_picking(return_internal_picking_type, return_location, factory_location, prev_move=picking and picking.move_lines, move_date=date_of_delivering_to_factory)
                # used > return > customer
                picking = self._create_picking(return_internal_picking_type, used_location, return_location)
                self._create_picking(outgoing_picking_type, return_location, self.customer_location_id, prev_move=picking and picking.move_lines)
                # factory > return > customer
                picking = self._create_picking(return_internal_picking_type, factory_location, return_location, move_date=date_of_repair_completion)
                self._create_picking(outgoing_picking_type, return_location, self.customer_location_id, prev_move=picking and picking.move_lines, move_date=date_of_repair_completion)
                # customer > return > used
                picking = self._create_picking(incoming_picking_type, self.customer_location_id, return_location, move_date=date_of_repair_completion)
                self._create_picking(return_internal_picking_type, return_location, used_location, prev_move=picking and picking.move_lines, move_date=date_of_repair_completion)
            else:
                # customer > factory
                self._create_picking(incoming_picking_type, self.customer_location_id, factory_location, move_date=date_of_delivering_to_factory)
                # used > return > customer
                picking = self._create_picking(return_internal_picking_type, used_location, return_location)
                self._create_picking(outgoing_picking_type, return_location, self.customer_location_id, prev_move=picking and picking.move_lines)
                # factory > customer
                self._create_picking(outgoing_picking_type, factory_location, self.customer_location_id, move_date=date_of_repair_completion)
                # customer > return > used
                picking = self._create_picking(incoming_picking_type, self.customer_location_id, return_location, move_date=date_of_repair_completion)
                self._create_picking(return_internal_picking_type, return_location, used_location, prev_move=picking and picking.move_lines, move_date=date_of_repair_completion)

        else:
            raise UserError('Invalid operation type.')

        assigned_user = self.ticket_id.user_id
        if assigned_user:
        # Create a reminder.
        self.ticket_id.activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            summary='Check the repair process.',
                user_id=assigned_user.id,
            date_deadline=date_of_repair_completion,
        )

    def _create_picking(self, picking_type, src_location, dst_location, prev_move=None, move_date=None):
        """Return a new picking or None (the latter if the source and the destination is the same place)."""
        self.ensure_one()

        picking_type.ensure_one()
        src_location.ensure_one()
        dst_location.ensure_one()

        assert picking_type._name == 'stock.picking.type'
        assert src_location._name == 'stock.location'
        assert dst_location._name == 'stock.location'
        assert prev_move is None or (prev_move._name == 'stock.move' and len(prev_move) == 1)
        assert move_date is None or isinstance(move_date, date)

        if src_location == dst_location:
            return None

        move_values = {
            'name': self.ticket_id.display_name,
            'company_id': self.ticket_id.company_id.id,
            'location_id': src_location.id,
            'location_dest_id': dst_location.id,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': 1,
            'helpdesk_repair_lot_id': self.lot_id.id,
        }

        picking_values = {
            'user_id': self.ticket_id.user_id.id,
            'picking_type_id': picking_type.id,
            'origin': self.ticket_id.display_name,
            'location_id': src_location.id,
            'location_dest_id': dst_location.id,
        }

        if move_date is not None:
            picking_values['scheduled_date'] = move_date
            move_values['date_expected'] = move_date
            move_values['date'] = move_date

        if prev_move is not None:
            move_values['move_orig_ids'] = [(4, prev_move.id)]

        picking = self.env['stock.picking'].sudo().create(dict(picking_values, move_lines=[(0, 0, move_values)]))

        picking.action_confirm()
        picking.action_assign()

        self.ticket_id.picking_ids = [(4, picking.id)]

        return picking
