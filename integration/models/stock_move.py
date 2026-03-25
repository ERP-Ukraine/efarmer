# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from odoo.tools import float_compare


# States that Odoo counts in incoming_qty / outgoing_qty when computing virtual_available.
# Mirrors the domain used in product._compute_quantities_dict().
VIRTUAL_AVAILABLE_STATES = frozenset(['waiting', 'confirmed', 'partially_available', 'assigned'])

# Move fields whose change can affect virtual_available (forecasted quantity).
VIRTUAL_AVAILABLE_AFFECTING_FIELDS = frozenset(['product_uom_qty', 'state', 'location_id', 'location_dest_id'])


class StockMove(models.Model):
    _inherit = 'stock.move'

    integration_external_id = fields.Char(
        related='sale_line_id.integration_external_id',
    )

    @property
    def has_kits(self):
        return any(getattr(x, 'bom_line_id', False) for x in self)

    def _assign_picking_post_process(self, *args, **kwargs):
        result = super()._assign_picking_post_process(*args, **kwargs)

        for picking in self.mapped('picking_id'):
            integration = picking.sale_id.integration_id

            if integration:
                source_note_name = integration.so_delivery_note_field.name
                target_note_name = integration.picking_delivery_note_field.name

                if source_note_name and target_note_name:
                    value = getattr(picking.sale_id, source_note_name)

                    if value:
                        picking.write({target_note_name: value})

        return result

    def _move_qty_lack(self):
        return self.compare_qty_to_realqty == -1

    def _has_enough_qty(self):
        return self.compare_qty_to_realqty <= 0

    @property
    def compare_qty_to_realqty(self):
        return float_compare(
            self.quantity,
            self.product_qty,
            precision_rounding=self.product_id.uom_id.rounding,
        )

    def _export_virtual_available(self):
        """Trigger virtual_available inventory export directly from moves.

        Called when move state changes affect virtual_available (forecasted quantity)
        without a corresponding stock.quant change (e.g., incoming moves confirmed/cancelled).
        Mirrors template-gathering logic of stock.quant.trigger_export().
        """
        integrations = self.env['sale.integration'].get_integrations('export_inventory')
        integrations = integrations.filtered(
            lambda i: i.synchronise_qty_field == 'virtual_available'
        )
        if not integrations:
            return

        templates = self.env['product.template']
        for product in self.mapped('product_id'):
            templates |= product.product_tmpl_id
            templates |= product.get_bom_parent_templates_recursively()
        templates = templates.filtered(lambda t: t.integration_should_export_inventory)

        if not templates:
            return

        for template in templates:
            if template.company_id:
                relevant = integrations.filtered(lambda i: i.company_id == template.company_id)
            else:
                relevant = integrations
            for integration in relevant:
                template._export_inventory_on_template(integration.id)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        # Edge case: moves created directly in an active state (e.g. via copy() or
        # programmatic flows). Draft moves are excluded — they don't affect virtual_available.
        active_moves = moves.filtered(lambda m: m.state in VIRTUAL_AVAILABLE_STATES)
        if active_moves:
            active_moves._export_virtual_available()
        return moves

    def write(self, vals):
        if not VIRTUAL_AVAILABLE_AFFECTING_FIELDS & set(vals.keys()):
            return super().write(vals)

        new_state = vals.get('state')

        # Guard: if no virtual_available integrations exist, skip all extra work.
        # Checked before pre-cancel state capture to avoid unnecessary iteration.
        # Uses the same get_integrations() pattern as stock.quant.trigger_export().
        has_va_integrations = bool(
            self.env['sale.integration'].get_integrations('export_inventory').filtered(
                lambda i: i.synchronise_qty_field == 'virtual_available'
            )
        )
        if not has_va_integrations:
            return super().write(vals)

        # Capture pre-write incoming active moves before state→cancel removes them.
        # Outgoing cancellations are handled by the quant trigger (reserved_qty released).
        pre_cancel_incoming_active = self.env['stock.move']
        if new_state == 'cancel':
            pre_cancel_incoming_active = self.filtered(
                lambda m: m.state in VIRTUAL_AVAILABLE_STATES
                and m.picking_type_id.code == 'incoming'
            )

        res = super().write(vals)

        if new_state:
            if new_state in VIRTUAL_AVAILABLE_STATES:
                # Moves became active (e.g. draft → confirmed): now counted in virtual_available.
                # Covers incoming moves (receipts) which never get quant reservations.
                moves_to_export = self.filtered(lambda m: m.state in VIRTUAL_AVAILABLE_STATES)
            elif new_state == 'cancel':
                # Outgoing cancellations: quant.reserved_quantity released → quant trigger fires.
                # Incoming cancellations: no quant reservation → trigger explicitly here.
                moves_to_export = pre_cancel_incoming_active
            else:
                # state → 'done': quant trigger fires (quant created/updated) — skip here.
                moves_to_export = self.env['stock.move']
        else:
            # Non-state field changed (product_uom_qty, location): only active moves matter.
            moves_to_export = self.filtered(lambda m: m.state in VIRTUAL_AVAILABLE_STATES)

        if moves_to_export:
            moves_to_export._export_virtual_available()

        return res
