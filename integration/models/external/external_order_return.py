# See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict
from copy import deepcopy

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError

from ...exceptions import ErrorStore as es


_logger = logging.getLogger(__name__)


class ExternalOrderReturn(models.Model):
    _name = 'external.order.return'
    _inherit = 'external.order.resource'
    _description = 'External Order Return'

    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('canceled', 'Canceled'),
            ('declined', 'Declined'),
        ],
        string='Status',
        default='open',
        required=True,
    )
    return_reason_summary = fields.Char(
        string='Return Reasons',
        help='Comma-joined reasons across lines (display only)',
    )
    reverse_tracking_number = fields.Char(
        string='Tracking Number',
    )
    reverse_tracking_url = fields.Char(
        string='Tracking URL',
    )
    reverse_tracking_carrier = fields.Char(
        string='Tracking Carrier',
    )
    line_ids = fields.One2many(
        comodel_name='external.order.return.line',
        inverse_name='return_id',
        string='Return Lines',
    )
    data_hash = fields.Char(
        string='Data Hash',
    )
    external_timestamp = fields.Datetime(
        string='External Timestamp',
    )
    picking_ids = fields.Many2many(
        comodel_name='stock.picking',
        string='Return Pickings',
        help='Return pickings created in Odoo',
    )
    restocked_externally = fields.Boolean(
        string='Restocked Externally',
        default=False,
        help='The platform reports the returned goods are already back in '
             'sellable stock (e.g. Shopify\'s "Refund + Restock" action). When '
             'set, the return picking is validated immediately on creation '
             'instead of waiting for the warehouse to receive the goods. Regular '
             'returns (goods still in transit from the customer) leave this '
             'unset, so their picking stays in Ready until physically received.',
    )

    def _compute_is_ecommerce_ok(self):
        """A return is always processable once its state is set: every value of the
        `state` Selection maps to a real action in `_process()` (create or cancel
        a return picking). New states added to the Selection must also be handled
        in `_process()` to remain consistent with this contract.
        """
        for rec in self:
            rec.is_ecommerce_ok = bool(rec.state)

    def write(self, vals):
        """Re-open an already-processed return when the platform pushes a new
        state onto it, so the connector acts on the change (validate the return
        transfer when the platform closes the return — "Process and refund" —
        or cancel it when the return is canceled/declined).

        Only the incoming-state write from `_get_or_create_from_external` carries
        `state`; internal bookkeeping writes (`mark_done`, `internal_info`,
        `picking_ids`, …) don't, so they never trigger this and there's no loop.
        Only `done` records are re-opened: `failed` records are already retried on
        every dispatch (the dispatch filter is `not is_done`), and `skipped` is a
        deliberate merchant "ignore" we don't override. The reset to `draft` makes
        the next `_process_external_returns` pass pick the record up again; the
        existing transfer is reused (validated/canceled), not recreated.
        """
        reopen = self.browse()
        if 'state' in vals and 'internal_status' not in vals:
            reopen = self.filtered(
                lambda r: r.internal_status == 'done' and r.state != vals['state']
            )

        res = super().write(vals)

        if reopen:
            for rec in reopen:
                _logger.info(
                    'Return %s: platform state changed to "%s" after processing — '
                    're-opening to act on the change.',
                    rec.external_str_id, rec.state,
                )
            reopen.write({'internal_status': 'draft'})

        return res

    def _prepare_vals_from_external(self, data: dict) -> dict:
        vals = deepcopy(data)

        # Convert nested line dicts into ORM commands
        lines = vals.pop('lines', [])
        vals['line_ids'] = [(5,)] + [(0, 0, x) for x in lines]

        return vals

    def _validate(self):
        """Entry point for return processing. Returns (bool, list)
        per parent class validate() contract.

        Distinguishes two failure modes:
        - PrerequisiteNotMet (soft fail): record stays in 'draft' for
          later retry when prerequisites are met (e.g. no done outgoing
          picking yet). Logged at INFO, not marked as failed.
        - UserError (hard fail): actual data/config error that won't
          auto-resolve. Record marked as failed, logged as warning.
        """
        self.ensure_one()

        # Terminal states: already processed, or intentionally skipped (e.g. a merchant
        # Skip). Return before touching internal_info so any existing note is preserved
        # and the record is not reprocessed. A skipped record is still processed when the
        # merchant forces it from the Apply button: Skip -> validate the delivery ->
        # come back and apply the return is the intended flow.
        was_skipped = self.internal_status == 'skipped'
        forced = self.env.context.get('integration_force_validate')

        if self.is_done or (was_skipped and not forced):
            return True, []

        # Drop the skip so the tail below can reach mark_done(). Every failure path below
        # restores it: a record skipped to unblock delivery validation must not re-enter
        # the pending set and re-block the outgoing picking on a failed apply.
        if was_skipped:
            self.internal_status = 'draft'

        self.internal_info = False
        try:
            self._process()
        except es.PrerequisiteNotMet as ex:
            # Soft fail: prerequisites not yet met. Record stays in draft for later retry.
            # Log at INFO so user understands why pending.
            self.internal_info = str(ex)
            if was_skipped:
                self.internal_status = 'skipped'
            _logger.info(
                '%s %s: deferred — %s',
                self._description, self.external_str_id, ex,
            )
            return False, []
        except es.UserError as ex:
            # Hard fail: actual error. Mark failed, log loudly. A forced apply keeps its
            # skip instead — 'failed' is retried on every automatic dispatch.
            self.internal_info = ex.args[0]
            if was_skipped:
                self.internal_status = 'skipped'
            else:
                self.mark_failed()
            return False, []

        # Don't overwrite a 'skipped' status set during _process() with 'done'.
        if self.internal_status != 'skipped':
            self.mark_done()
        return True, []

    def _process(self):
        """Drive the return through its lifecycle states.

        open / closed: ensure a return transfer exists (idempotent). The transfer
        is then validated when the goods are physically back — i.e. the platform
        closed the return ("Process and refund"), or it was a refund-with-restock
        (`restocked_externally`). A regular open return leaves its transfer in
        Ready until the warehouse receives the goods.

        canceled / declined: cancel the pending return transfer.

        State changes after the return was already processed re-enter here via the
        `write()` re-open hook, so the same branch validates or cancels the
        existing transfer instead of creating a new one.
        """
        self.ensure_one()

        if self.state in ('open', 'closed'):
            # Idempotent: creates the transfer if missing, reuses it otherwise
            # (e.g. on a re-open after the platform closed an already-open return).
            self._create_return_picking()
            if self.state == 'closed' or self.restocked_externally:
                self._validate_return_pickings()
        elif self.state in ('canceled', 'declined'):
            self._handle_cancel_or_decline()
        else:
            es.raise_error(
                err_code='E561',
                err_msg=_(
                    'Return %(name)s has unknown state "%(state)s". '
                    'Cannot process. Manual review required.',
                    name=self.name or self.external_str_id,
                    state=self.state,
                ),
                support_contact=False,
            )

    def _create_return_picking(self):
        """Create return picking(s) via the stock.return.picking wizard.

        Lines are grouped by external_fulfillment_str_id — each group creates a return picking
        against the corresponding outgoing picking (multi-picking partition). Lines without
        fulfillment info fall back to a single-picking flow that matches all order line ids
        against the only done outgoing picking.
        """
        self.ensure_one()

        # Idempotency: check if a return picking already exists
        existing_return_pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming' and p.state != 'cancel'
        )
        if existing_return_pickings:
            _logger.info(
                'Return %s: return picking already created (%s). Skipping.',
                self.external_str_id,
                existing_return_pickings[0].name,
            )
            return

        order = self.erp_order_id

        # Soft fail: a return cannot be processed before the original delivery is validated.
        # Retried when the outgoing picking moves to 'done' via the lifecycle hook on
        # stock.picking._action_done.
        done_outgoing = order.picking_ids.filtered(
            lambda p: p.state == 'done'
            and p.picking_type_id.code == 'outgoing'
        )
        if not done_outgoing:
            es.raise_error(
                err_code='E516',
                err_msg=_(
                    'Cannot create return picking for %(return_name)s: '
                    'order %(order_name)s has no completed delivery picking. '
                    'A return cannot be processed before the original delivery '
                    'is validated. Will retry when delivery is validated.',
                    return_name=self.name or self.external_str_id,
                    order_name=order.name,
                ),
                support_contact=False,
            )

        # Group return lines by which fulfillment they came from. Each group creates a return
        # picking against the corresponding outgoing picking. Lines without fulfillment data
        # (empty key) fall back to the single-picking flow further below.
        groups = defaultdict(list)
        for line in self.line_ids:
            key = line.external_fulfillment_str_id or ''
            groups[key].append(line)

        # Resolve restock location (shared across all pickings)
        restock_location = self._resolve_restock_location()

        for fulfillment_str_id, lines in groups.items():
            source_picking = self._resolve_outgoing_picking_for_fulfillment(
                fulfillment_str_id, done_outgoing,
            )
            if not source_picking:
                es.raise_error(
                    err_code='E562',
                    err_msg=_(
                        'Cannot create return picking for %(return_name)s: '
                        'order %(order_name)s has no completed delivery picking '
                        'for fulfillment %(fulfillment)s. '
                        'A return cannot be processed before the original delivery '
                        'is validated. Validate the delivery picking first, then '
                        'retry this return job.',
                        return_name=self.name or self.external_str_id,
                        order_name=order.name,
                        fulfillment=fulfillment_str_id or '(unknown)',
                    ),
                    support_contact=False,
                )

            adopted = self._check_return_conflict(source_picking, lines)
            if adopted:
                _logger.info(
                    'Return %s: adopting existing open return picking %s '
                    '(matches the incoming external return; not creating a duplicate).',
                    self.external_str_id, adopted.name,
                )
                self.picking_ids = [(4, adopted.id)]
                continue

            new_picking = self._create_single_return_picking(
                source_picking, lines, restock_location,
            )
            self.picking_ids = [(4, new_picking.id)]

    def _create_single_return_picking(self, source_picking, lines, restock_location):
        """Create one return picking against a source outgoing picking."""
        wizard = self.env['stock.return.picking'].with_context(
            active_id=source_picking.id,
            active_model='stock.picking',
        ).create({})

        self._populate_wizard_lines_for_subset(wizard, source_picking, lines)

        new_picking = wizard._create_return()

        if restock_location:
            new_picking.write({'location_dest_id': restock_location.id})

        self._apply_reverse_shipping_info(new_picking)

        # TODO: use the external return date instead of Odoo's default (creation/validation
        # time). Consistent with the existing fulfillment pattern, but may be incorrect for
        # historical imports. Deferred to avoid asymmetric scenarios where delivery is created
        # today but return is backdated.

        return new_picking

    def _validate_return_pickings(self):
        """Validate the return's incoming transfers because the goods are now
        physically back — either the platform closed the return ("Process and
        refund") or it was a refund-with-restock. Called from `_process()` for the
        `closed` state and for `restocked_externally` returns; a regular open
        return doesn't call it and its transfer stays in Ready until the warehouse
        receives the goods.
        """
        pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'incoming'
            and p.state not in ('done', 'cancel')
        )
        for picking in pickings:
            self._validate_single_return_picking(picking)

    def _validate_single_return_picking(self, picking):
        """Validate one return transfer, best-effort.

        If validation cannot complete (e.g. a lot/serial-tracked product needs
        manual lot assignment, or button_validate returns a wizard instead of
        finishing), the picking is left in its current state and a warning is
        logged so the warehouse can finish it by hand. The return is never blocked
        on this step.

        Incoming return pickings don't re-enter entity dispatch (the _action_done
        hook only fires for outgoing pickings), but skip_external_entity_dispatch
        is passed defensively to match the credit-note/payment posting pattern.
        """
        if picking.state in ('done', 'cancel'):
            return

        try:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
            picking.with_context(
                skip_backorder=True,
                skip_sms=True,
                skip_external_entity_dispatch=True,
            ).button_validate()
        except (UserError, ValidationError) as ex:
            _logger.warning(
                'Return %s: could not auto-validate return picking %s (%s). '
                'Leaving it in "%s" for manual completion.',
                self.external_str_id, picking.name, ex, picking.state,
            )
            return

        if picking.state != 'done':
            _logger.warning(
                'Return %s: return picking %s did not reach "done" after '
                'auto-validation (still "%s"); leaving for manual completion.',
                self.external_str_id, picking.name, picking.state,
            )

    def _apply_reverse_shipping_info(self, picking):
        """Copy reverse-shipment carrier + tracking from the external return onto the new
        incoming picking. Carrier name is resolved via the same lookup the fulfillment path
        uses; an unmapped carrier name is left empty (no write) rather than failing.
        """
        if self.reverse_tracking_number:
            picking.carrier_tracking_ref = self.reverse_tracking_number

        if self.reverse_tracking_carrier:
            carrier = self.env['delivery.carrier']._get_carrier_by_external_name(
                self.integration_id,
                self.reverse_tracking_carrier,
            )
            if carrier:
                picking.carrier_id = carrier.id

    def _resolve_outgoing_picking_for_fulfillment(self, fulfillment_str_id, done_outgoing):
        """Find the outgoing picking corresponding to a given fulfillment.

        Resolution order:
          1. fulfillment.picking_id (the cached primary path).
          2. fulfillment._get_pickings() (re-derive — narrow timing window).
          3. _find_matching_outgoing_picking_legacy (match by returned products).

        The legacy fallback also runs when fulfillment_str_id is empty (return line had no
        fulfillment data), the fulfillment record cannot be found, or fulfillment.picking_id
        was never populated (e.g. the outgoing picking was already validated before fulfillment
        processing ran).
        """
        if not fulfillment_str_id:
            return self._find_matching_outgoing_picking_legacy(done_outgoing)

        fulfillment = self.env['external.order.fulfillment'].search([
            ('external_str_id', '=', fulfillment_str_id),
            ('integration_id', '=', self.integration_id.id),
        ], limit=1)

        if not fulfillment:
            return self._find_matching_outgoing_picking_legacy(done_outgoing)

        # Primary path: use cached picking_id
        if fulfillment.picking_id and fulfillment.picking_id.state == 'done':
            return fulfillment.picking_id

        # Secondary fallback: re-derive via existing chain. Note that _get_pickings() filters
        # for confirmed/assigned pickings only, so this only succeeds in rare timing windows.
        # Most cases where picking_id is empty fall through to the legacy fallback below.
        pickings = fulfillment._get_pickings().filtered(
            lambda p: p.state == 'done'
        )
        if pickings:
            return pickings[:1]

        # fulfillment.picking_id was never populated (e.g. the outgoing picking was validated
        # before fulfillment processing ran). Fall through to the legacy resolution against
        # the order's done outgoing pickings.
        return self._find_matching_outgoing_picking_legacy(done_outgoing)

    def _find_matching_outgoing_picking_legacy(self, done_outgoing):
        """Match-by-product fallback: find the done outgoing picking whose
        moves cover all returned products. Used when fulfillment data is
        unavailable or didn't resolve to a single picking.
        """
        if len(done_outgoing) == 1:
            return done_outgoing

        returned_products = set()
        for return_line in self.line_ids:
            product = self._resolve_return_line_to_product(return_line)
            if product:
                returned_products.add(product.id)

        for picking in done_outgoing.sorted('date_done', reverse=True):
            picking_products = set(picking.move_ids.mapped('product_id.id'))
            if returned_products <= picking_products:
                return picking

        # Fallback to most recent if no single picking covers all products
        return done_outgoing.sorted('date_done', reverse=True)[0]

    def _populate_wizard_lines(self, wizard, original_picking):
        """Set return quantities on wizard lines matching our return lines.
        Kept for backwards compatibility. Delegates to subset method."""
        self._populate_wizard_lines_for_subset(
            wizard, original_picking, self.line_ids,
        )

    def _populate_wizard_lines_for_subset(
        self, wizard, original_picking, lines,
    ):
        """Set return quantities on the wizard's product_return_moves for a
        subset of this return's lines. Raises if a return line cannot be
        resolved to a product (no SO line with matching
        integration_external_id) — fail-loud, since silently skipping the
        line would create a zero-line return picking.

        Kit (phantom BoM) products: the external payload counts kit parents
        (e.g., "1 Chair"), but the picking's wizard lines are component-level
        moves (Seat + Backrest + Legs). For kits, we explode the parent qty
        into per-component quantities via the same `bom_kit.explode()` channel
        the fulfillment path uses, then set each component's wizard line.
        """
        for return_line in lines:
            product = self._resolve_return_line_to_product(return_line)
            if not product:
                es.raise_error(
                    err_code='E517',
                    err_msg=_(
                        'Cannot create return picking for %(return_name)s: '
                        'return line %(line_id)s could not be resolved to a product. '
                        'No matching sale order line found with '
                        'integration_external_id=%(ext_id)s on order %(order)s.',
                        return_name=self.name or self.external_str_id,
                        line_id=return_line.external_str_id or '',
                        ext_id=return_line.external_line_str_id or '',
                        order=self.erp_order_id.name,
                    ),
                    support_contact=False,
                )

            bom_kit = self._get_kit_bom(product)
            if bom_kit:
                qty_per_component = self._explode_kit_quantities(
                    bom_kit, product, return_line.quantity,
                )
                # Require ALL kit components to match the wizard. A partial
                # match (e.g. seat+backrest matched, legs missing because the
                # BoM was edited after shipping) would produce a return
                # picking with a partial composition that does not represent
                # what the customer returned.
                unmatched = []
                for cmp_id, cmp_qty in qty_per_component.items():
                    wl = wizard.product_return_moves.filtered(
                        lambda ln, cmp_id=cmp_id: ln.product_id.id == cmp_id
                    )
                    if wl:
                        wl[0].write({'quantity': cmp_qty, 'to_refund': True})
                    else:
                        unmatched.append(cmp_id)
                if unmatched:
                    missing_products = self.env['product.product'].browse(unmatched)
                    missing_names = ', '.join(missing_products.mapped('display_name'))
                    es.raise_error(
                        err_code='E518c',
                        err_msg=_(
                            'The return for order %(order)s includes a kit product '
                            '("%(product)s") whose components could not all be matched '
                            'to the delivery (missing on the picking: %(missing)s). '
                            'This can happen if the product\'s kit setup changed after '
                            'the order shipped. Please process this return manually in '
                            'Odoo, or contact support.',
                            order=self.erp_order_id.name,
                            product=product.display_name,
                            missing=missing_names,
                        ),
                        support_contact=False,
                    )
                continue

            # Non-kit: a single wizard line for this product.
            wizard_line = wizard.product_return_moves.filtered(
                lambda ln, product=product: ln.product_id.id == product.id
            )
            if wizard_line:
                # to_refund=True is set explicitly. qty_delivered (net physical movement) and
                # qty_invoiced (net finance) on SO lines are independent: to_refund corrects
                # qty_delivered when the return picking is validated, and the credit note
                # corrects qty_invoiced — each side is corrected independently, not
                # double-counted. Set explicitly to document intent and guard against future
                # Odoo default changes.
                wizard_line[0].write({
                    'quantity': return_line.quantity,
                    'to_refund': True,
                })

    def _get_kit_bom(self, product):
        """Return the phantom BoM for `product` if one exists, else False.
        Cached lookup via mrp.bom._bom_find — same channel used by the
        fulfillment path in stock_picking._validate_external_fulfillment.
        """
        return self.env['mrp.bom']._bom_find(product, bom_type='phantom')[product]

    def _explode_kit_quantities(self, bom_kit, product, parent_qty):
        """Explode a kit parent quantity into a {component_product_id: qty}
        dict. Mirrors the fulfillment kit explode pattern. The `int()` cast
        on component qty matches the fulfillment side — non-integer BoM
        ratios on partial returns are a known limitation.
        """
        __, bom_sub_lines = bom_kit.explode(product, parent_qty)
        return {bl.product_id.id: int(dct['qty']) for (bl, dct) in bom_sub_lines}

    def _check_return_conflict(self, source_picking, lines):
        """Inspect existing return pickings on `source_picking` against the
        incoming return composition. Three outcomes:

        - Returns a `stock.picking` record: an existing open return picking
          matches the incoming external return (same SO lines, same per-line
          quantities). The caller adopts it instead of creating a duplicate.
        - Returns False / empty record: clear to proceed with a new picking.
        - Raises E518a / E518b: a conflict that needs user action.

        Quantity comparison happens at sale.order.line granularity. For kit
        SO lines (phantom BoM), the comparison is in parent units — kit
        explode result is used to convert open-return component qty back to
        parent units.
        """
        self.ensure_one()
        no_picking = self.env['stock.picking']

        requested_by_sl = self._group_lines_by_sale_line(lines)
        if not requested_by_sl:
            return no_picking

        # Open return pickings already on this source. self.picking_ids was
        # short-circuited upstream, so any open return here belongs either to
        # another external.order.return record (concurrent webhooks) or to a
        # manual picking with no external record. M2M timing safety net: still
        # subtract self.picking_ids.
        open_returns = source_picking.return_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        open_returns -= self.picking_ids

        # 1. Adoption first. If an existing open picking has the same SO-line
        #    composition as the incoming external return, adopt it — both refer
        #    to the same physical movement so creating a second picking would
        #    double-count.
        for op in open_returns:
            composition = self._composition_of_picking(op)
            if self._compositions_match(composition, requested_by_sl):
                return op

        # 2. Quota check. _remaining_returnable_qty already subtracts validated
        #    returns (via qty_delivered) and open-return moves (explicit). Order
        #    matters: this MUST run after the adoption check, otherwise a
        #    matching open picking counts twice (as already-committed AND as
        #    about-to-be-created).
        for sl_id, requested_qty in requested_by_sl.items():
            sale_line = self.env['sale.order.line'].browse(sl_id)
            remaining = self._remaining_returnable_qty(sale_line)
            rounding = sale_line.product_uom_id.rounding or 0.01
            if requested_qty - remaining > rounding:
                es.raise_error(
                    err_code='E518b',
                    err_msg=_(
                        'Cannot create a return for order %(order)s: '
                        'returning %(qty)s units of %(product)s would exceed '
                        'the quantity that can still be returned '
                        '(%(remaining)s remaining; the rest has already been '
                        'returned). Please review the existing returns on '
                        'this order.',
                        order=self.erp_order_id.name,
                        qty=requested_qty,
                        product=sale_line.product_id.display_name,
                        remaining=remaining,
                    ),
                    support_contact=False,
                )

        # 3. Quota fits, but a non-matching open return exists — the user
        #    must resolve it before this new return can be processed.
        if open_returns:
            picking_names = ', '.join(open_returns.mapped('name'))
            es.raise_error(
                err_code='E518a',
                err_msg=_(
                    'This order already has a return in progress that '
                    'does not match the return received from the store. '
                    'Please review the existing return on order '
                    '%(order)s (picking %(picking)s) and resolve it '
                    'before this return can be processed.',
                    order=self.erp_order_id.name,
                    picking=picking_names,
                ),
                support_contact=False,
            )

        return no_picking

    def _group_lines_by_sale_line(self, lines):
        """Resolve each return line to its sale.order.line, summing qty per
        SO line. Returned dict maps sale.order.line.id → total requested qty
        (in the SO line's product UoM — parent units for kits).
        """
        result = defaultdict(float)
        for return_line in lines:
            sale_line = self._resolve_return_line_to_sale_line(return_line)
            if not sale_line:
                # Will fail later in _populate_wizard_lines_for_subset with E517.
                continue
            result[sale_line.id] += return_line.quantity
        return result

    def _resolve_return_line_to_sale_line(self, return_line):
        """Find the sale.order.line on this return's parent order whose
        integration_external_id matches the return line's source-line ID.
        Returns False if no match — caller handles the fail-loud.
        """
        if not return_line.external_line_str_id:
            return False
        for so_line in self.erp_order_id.order_line:
            if not so_line.product_id:
                continue
            if so_line.integration_external_id == return_line.external_line_str_id:
                return so_line
        return False

    def _remaining_returnable_qty(self, sale_line):
        """Remaining quantity that can still be returned for this SO line.

        Counts ALL non-cancelled open-return moves for this SO line,
        regardless of the ``to_refund`` flag. A user who creates a manual
        return via Odoo's native wizard without ticking "to refund" would
        otherwise slip past the over-return guard (E518b) — duplicate return
        picking, or wizard quantities go negative. Consistent with
        ``_composition_of_picking`` (which also ignores ``to_refund``).

        qty_delivered (with sale_mrp installed) is in the SO line's product
        UoM — parent units for kit lines — and already nets out VALIDATED
        returns whose moves have to_refund=True. OPEN (not-yet-validated)
        return pickings must be subtracted explicitly because their goods
        haven't been received yet but the quantity is already committed.

        For kit lines, open-return component moves are converted back to
        parent units via the move's bom_line_id ratio. For non-kit lines,
        move qty is used directly.
        """
        delivered = sale_line.qty_delivered

        # Open return moves linked to this SO line on any non-cancelled
        # return picking. Moves on cancelled pickings inherit state='cancel'
        # so the filter on move.state suffices.
        open_states = ('draft', 'waiting', 'confirmed', 'partially_available', 'assigned')
        open_moves = self.env['stock.move'].search([
            ('sale_line_id', '=', sale_line.id),
            ('state', 'in', open_states),
            ('picking_id.return_id', '!=', False),
        ])

        open_in_parent_units = 0.0
        for mv in open_moves:
            if mv.bom_line_id:
                # Component of a kit. Convert component qty back to parent units.
                ratio = mv.bom_line_id.product_qty or 1.0
                open_in_parent_units += mv.product_uom_qty / ratio
            else:
                open_in_parent_units += mv.product_uom_qty

        return delivered - open_in_parent_units

    def _composition_of_picking(self, picking):
        """Build a {sale_line_id: total_qty_in_parent_units} dict describing
        the given return picking's moves. Used to compare an existing
        open-return picking against the incoming external return for the
        adoption path.

        Non-kit moves contribute their product_uom_qty directly. Kit
        component moves (move.bom_line_id set) are converted back to parent
        units (qty / bom_line.product_qty). Multiple components of the same
        kit all map to the same parent count when the picking is well-formed;
        we take min() across components as defence against partial wizard
        edits.
        """
        active = picking.move_ids.filtered(
            lambda m: m.state != 'cancel' and m.sale_line_id
        )
        non_kit = active.filtered(lambda m: not m.bom_line_id)
        kit = active - non_kit

        composition = defaultdict(float)
        for mv in non_kit:
            composition[mv.sale_line_id.id] += mv.product_uom_qty

        kit_sl_ids = set(kit.mapped('sale_line_id.id'))
        for sl_id in kit_sl_ids:
            parent_counts = [
                m.product_uom_qty / (m.bom_line_id.product_qty or 1.0)
                for m in kit.filtered(lambda m, sl_id=sl_id: m.sale_line_id.id == sl_id)
            ]
            composition[sl_id] = min(parent_counts)

        return dict(composition)

    def _compositions_match(self, composition_a, composition_b):
        """Compare two {sale_line_id: qty} dicts for equality with a UoM
        rounding tolerance. Returns True iff they cover the same SO lines
        with the same quantities (per the SO line's product UoM rounding).
        """
        if set(composition_a.keys()) != set(composition_b.keys()):
            return False
        for sl_id, qty_a in composition_a.items():
            qty_b = composition_b.get(sl_id, 0.0)
            sale_line = self.env['sale.order.line'].browse(sl_id)
            rounding = sale_line.product_uom_id.rounding or 0.01
            if abs(qty_a - qty_b) > rounding:
                return False
        return True

    def _resolve_return_line_to_product(self, return_line):
        """Resolve the Odoo product for a return line by matching
        return_line.external_line_str_id against sale.order.line.integration_external_id on
        the parent order. Both store the connector's bare external id (numeric), so the
        comparison is direct equality.
        """
        if not return_line.external_line_str_id:
            return False

        for so_line in self.erp_order_id.order_line:
            if not so_line.product_id:
                continue
            if so_line.integration_external_id == return_line.external_line_str_id:
                return so_line.product_id

        return False

    def _resolve_restock_location(self):
        """Return the stock.location to use as restock destination.

        Currently only honours the integration-level default; fails-loud when
        unset. (A per-line external-location override is reserved for the
        reactive return-from-refund flow.)
        """
        self.ensure_one()
        integration = self.integration_id

        if integration.default_return_location_id:
            return integration.default_return_location_id

        es.raise_error(
            err_code='E505',
            err_msg=_(
                'Cannot create return picking for %(return_name)s: '
                'no restock location can be determined. Either configure '
                'stock location mapping for the external location or set '
                'Default Return Location in the integration\'s Returns & '
                'Refunds tab, then retry this job.',
                return_name=self.name or self.external_str_id,
            ),
            support_contact=False,
        )

    def _handle_cancel_or_decline(self):
        """Cancel pending return pickings when the platform-side return
        moves to canceled/declined. Fails-loud if any return picking is
        already validated ('done'), since goods were physically received
        and the user must reverse that manually.
        """
        self.ensure_one()

        if not self.picking_ids:
            return

        # done picking = goods received, can't auto-cancel.
        done_pickings = self.picking_ids.filtered(
            lambda p: p.state == 'done'
        )
        if done_pickings:
            es.raise_error(
                err_code='E511',
                err_msg=_(
                    'Return %(return_name)s was canceled on the platform but '
                    'the return picking is already validated in Odoo. '
                    'Goods were physically received. '
                    'Reverse manually if needed.',
                    return_name=self.name or self.external_str_id,
                ),
                support_contact=False,
            )

        # Cancel all non-done, non-canceled pickings
        cancelable = self.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        for picking in cancelable:
            picking.action_cancel()

    def cancel_in_ecommerce_system(self):
        raise NotImplementedError
