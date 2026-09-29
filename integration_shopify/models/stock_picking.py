# See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict

from odoo import api, fields, models, _

from odoo.addons.integration.exceptions import ErrorStore as es


_logger = logging.getLogger(__name__)


# Default ReturnReason sent to Shopify. Maps to the ReturnReason GraphQL enum
# value 'UNKNOWN'. Merchants can edit the reason in the Shopify admin after.
SHOPIFY_RETURN_REASON_DEFAULT = 'UNKNOWN'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_shopify_return_export_eligible = fields.Boolean(
        compute='_compute_is_shopify_return_export_eligible',
        help='True when this picking is a return on a Shopify-linked order '
             'with returns/refunds sync enabled. Used by the form view to '
             'gate the "Export to Shopify" button visibility.',
    )

    @api.depends('return_id', 'sale_id.integration_id.is_integration_shopify',
                 'sale_id.integration_id.enable_returns_refunds_sync')
    def _compute_is_shopify_return_export_eligible(self):
        for picking in self:
            sale_order = picking.sale_id or picking.return_id.sale_id
            integration = sale_order and sale_order.integration_id
            eligible = bool(
                picking.return_id
                and integration
                and integration.is_integration_shopify
                and integration.enable_returns_refunds_sync
            )
            # Hide the button once this picking has already been exported — a second
            # export is blocked by the E520 duplicate guard anyway, so showing it only
            # invites a confusing error. Non-stored field: recomputed on each form read,
            # so it flips to False as soon as the export creates the mapping record.
            if eligible and picking.id and self.env['external.order.return'].search_count([
                ('picking_ids', 'in', picking.id),
                ('external_str_id', '!=', False),
            ]):
                eligible = False
            picking.is_shopify_return_export_eligible = eligible

    @property
    def carrier_tracking_url_prop(self):
        self.ensure_one()
        return self.carrier_id.integration_send_tracking_url and self.carrier_tracking_url or False

    @property
    def is_done(self):
        self.ensure_one()
        return self.state == 'done'

    def to_export_format(self, integration: 'models.Model'):
        result = super().to_export_format(integration)

        if integration.is_integration_shopify:
            result['carrier_tracking_url'] = self.carrier_tracking_url_prop

        return result

    def to_export_format_multi(self, integration):
        result = super().to_export_format_multi(integration)

        if integration.is_integration_shopify:

            for data, picking in zip(result, self):
                data['carrier_tracking_url'] = picking.carrier_tracking_url_prop

        return result

    def button_validate(self):
        """
        Override button_validate method to called method, that check order is shipped or not.
        """
        res = super(StockPicking, self).button_validate()

        for record in self:
            if record.is_done:
                record._run_integration_picking_hooks()

        return res

    # ------------------------------------------------------------------
    # Return export to Shopify (logistics-only).
    # Refund movement stays in Shopify by design.
    # Loop prevention: the new external.order.return is created with the
    # Shopify GID + mark_done() in the same transaction as the mutation, so
    # the inbound returns/* webhook that fires shortly after finds the record
    # by GID and _validate() short-circuits on is_done.
    # ------------------------------------------------------------------

    def action_export_return_to_shopify(self):
        """Button handler. Delegates to the per-connector override."""
        self.ensure_one()
        external_return = self._export_return_to_ecommerce_system()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Return exported to Shopify'),
                'message': _('Shopify Return: %(gid)s', gid=external_return.external_str_id),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _export_return_to_ecommerce_system(self):
        """Connector dispatch. Only Shopify implements export in v1."""
        self.ensure_one()
        sale_order = self.sale_id or self.return_id.sale_id
        integration = sale_order and sale_order.integration_id
        if not integration or not integration.is_integration_shopify:
            es.raise_error(
                err_code='E521',
                err_msg=_(
                    'Return export to the e-commerce platform is only supported '
                    'for Shopify integrations. Picking %(picking)s.',
                    picking=self.name,
                ),
                support_contact=False,
            )
        return self._export_return_to_shopify()

    def _export_return_to_shopify(self):
        """Return export entry point. Mirrors the _action_cancel_integration shape:
        a short top-level method with numbered steps that delegate to focused
        helpers.
        """
        self.ensure_one()
        sale_order = self.sale_id or self.return_id.sale_id
        integration = sale_order.integration_id

        # 1. Pre-flight (kit refusal, duplicate guard).
        self._check_return_export_preflight()

        # 2. Build returnCreate input.
        return_line_items = self._build_return_export_lines(integration, sale_order)

        # 3. Call Shopify. returnCreate either returns a Return node (with
        #    its reverseFulfillmentOrder for tracking) or raises via the
        #    user_errors_path machinery.
        result = integration.adapter.create_return_for_order(
            sale_order.external_order_name, return_line_items,
        )

        # 4. Hard check: if the merchant wants tracking attached, Shopify must
        #    have returned a reverseFulfillmentOrder. Missing rFO means the
        #    follow-up mutation has nothing to attach to. We raise before
        #    creating the Odoo-side mapping row — the Shopify Return survives
        #    and the inbound returns/* webhook will reconcile.
        if self.carrier_tracking_ref and not result['reverse_fulfillment_order_id']:
            es.raise_error(
                err_code='E522',
                err_msg=_(
                    'Shopify created the return for picking %(picking)s but did '
                    'not return a reverseFulfillmentOrder. Tracking cannot be '
                    'attached. Add tracking to the return manually in the '
                    'Shopify admin.',
                    picking=self.name,
                ),
                support_contact=False,
            )

        # 5. Create the Odoo-side mapping record carrying the new Shopify
        #    Return id. mark_done() closes the inbound-webhook loop. The id is
        #    normalised to the bare numeric form (id_str) — exactly what the
        #    inbound returns/* parser stores — so the webhook that follows
        #    dedups against this row instead of creating a duplicate. Status
        #    'open' matches RETURN_STATUS_MAP for the OPEN/REQUESTED values
        #    returnCreate produces for merchant-initiated returns.
        return_id_str = integration.adapter.gql.Return.set(id=result['id']).id_str
        external_return = self.env['external.order.return'].create({
            'erp_order_id': sale_order.id,
            'external_str_id': return_id_str,
            'external_order_str_id': sale_order.external_order_name,
            'state': 'open',
            'picking_ids': [(4, self.id)],
        })
        external_return.mark_done()

        # 6. Tracking attachment (only when we have tracking — rFO was
        #    already validated in step 4). Best-effort: on failure the
        #    helper returns (False, err_msg) so the chatter can surface
        #    the failure without rolling back step 5.
        tracking_ok, tracking_error = (True, '')
        if self.carrier_tracking_ref:
            tracking_ok, tracking_error = self._attach_return_tracking_to_shopify(
                integration, sale_order,
                result['reverse_fulfillment_order_id'],
                result.get('reverse_fulfillment_order_line_items') or [],
            )

        # 7. Chatter.
        self._log_return_export_to_chatter(external_return, tracking_ok, tracking_error)

        return external_return

    def _check_return_export_preflight(self):
        """Hard fail on kit (E519) or already-exported (E520)."""
        self.ensure_one()

        # E519 — kit return export not supported in v1. Detection mirrors the
        # fulfillment-side check (getattr(move, 'bom_line_id', False)) — return
        # moves inherit bom_line_id from the source moves they copy.
        if any(m.bom_line_id for m in self.move_ids):
            order = self.sale_id or self.return_id.sale_id
            es.raise_error(
                err_code='E519',
                err_msg=_(
                    'Kit product returns cannot currently be exported to '
                    'Shopify. Please process this return manually in Shopify. '
                    '(Order %(order)s, return picking %(picking)s.)',
                    order=order and order.name or '?',
                    picking=self.name,
                ),
                support_contact=False,
            )

        # E520 — duplicate export attempt.
        existing = self.env['external.order.return'].search([
            ('picking_ids', 'in', self.id),
            ('external_str_id', '!=', False),
        ], limit=1)
        if existing:
            es.raise_error(
                err_code='E520',
                err_msg=_(
                    'This return has already been exported to Shopify '
                    '(Shopify Return %(gid)s). It cannot be exported a second '
                    'time. If something looks wrong with the existing Shopify '
                    'return, please correct it in Shopify directly.',
                    gid=existing.external_str_id,
                ),
                support_contact=False,
            )

    def _build_return_export_lines(self, integration, sale_order):
        """Return a list of returnLineItem dicts ready for Shopify's
        returnCreate input, keyed via SO line external id → FulfillmentLineItem GID(s).

        Re-fetches the FulfillmentLineItem lookup from Shopify at export time
        rather than persisting it on the Odoo side — avoids a migration for
        historical orders.

        A sale.order.line can map to more than one FulfillmentLineItem when the
        underlying order LineItem was shipped across multiple fulfillments
        (staged/partial shipments, e.g. a partial delivery followed by a
        backorder) — the requested quantity is then split across them, each
        capped at what that specific fulfillment line item can still return,
        producing one returnLineItem entry per fulfillment actually used.

        The per-fulfillment cap already accounts for quantity claimed by earlier
        returns (open or closed) — the lookup queries Shopify's returnableFulfillments,
        not raw fulfilled quantity — so exceeding what's left is caught here as E521
        rather than only surfacing when Shopify's returnCreate mutation rejects the call.
        """
        self.ensure_one()

        line_item_gid_to_flis = integration.adapter.fetch_fulfillment_line_item_lookup(
            sale_order.external_order_name,
        )

        qty_by_sale_line = defaultdict(float)
        for move in self.move_ids.filtered(lambda m: m.state != 'cancel' and m.sale_line_id):
            qty_by_sale_line[move.sale_line_id] += move.product_uom_qty

        LineItem = integration.adapter.gql.LineItem
        return_line_items = []
        unresolved = self.env['sale.order.line']
        for sale_line, qty in qty_by_sale_line.items():
            if qty <= 0:
                continue
            so_line_ext_id = sale_line.integration_external_id
            if not so_line_ext_id:
                unresolved |= sale_line
                continue

            line_item_gid = LineItem.create_gid(so_line_ext_id)
            available = line_item_gid_to_flis.get(line_item_gid) or []

            remaining = qty
            line_entries = []
            for fli_gid, fulfilled_qty in available:
                if remaining <= 0:
                    break
                take = min(remaining, fulfilled_qty)
                if take <= 0:
                    continue
                line_entries.append({
                    'fulfillmentLineItemId': fli_gid,
                    'quantity': int(take),
                    'returnReason': SHOPIFY_RETURN_REASON_DEFAULT,
                })
                remaining -= take

            if remaining > 0:
                # Either no fulfillment covers this line at all, or the requested quantity
                # exceeds what every fulfillment still has left to return (already reduced
                # for any earlier return, open or closed, claimed against it).
                unresolved |= sale_line
                continue

            return_line_items.extend(line_entries)

        if unresolved:
            line_names = ', '.join(unresolved.mapped('product_id.display_name'))
            es.raise_error(
                err_code='E521',
                err_msg=_(
                    'Cannot export return picking %(picking)s to Shopify: the '
                    'following lines could not be matched to a Shopify '
                    'FulfillmentLineItem, or the requested quantity exceeds what is still '
                    'returnable for them: %(lines)s. Either the order was imported before '
                    'fulfillment tracking existed, an earlier return already claimed this '
                    'quantity, or the data on Shopify has changed. Process this return '
                    'manually.',
                    picking=self.name,
                    lines=line_names,
                ),
                support_contact=False,
            )

        if not return_line_items:
            es.raise_error(
                err_code='E521',
                err_msg=_(
                    'Cannot export return picking %(picking)s: no returnable '
                    'lines could be built from this picking.',
                    picking=self.name,
                ),
                support_contact=False,
            )

        return return_line_items

    def _attach_return_tracking_to_shopify(
        self, integration, sale_order, reverse_fulfillment_order_gid,
        reverse_delivery_line_items,
    ):
        """Best-effort tracking attachment. Returns (success: bool, error: str).
        Failure does NOT roll back the created Return; the caller surfaces the
        error on chatter so the merchant can attach tracking directly in Shopify.

        Caller is responsible for guarding on `self.carrier_tracking_ref` and a
        non-empty `reverse_fulfillment_order_gid` — this method assumes both.
        `reverse_delivery_line_items` is the required, non-empty list of
        {reverseFulfillmentOrderLineItemId, quantity} from create_return().
        """
        self.ensure_one()

        # reverseDeliveryCreateWithShipping requires a non-empty reverseDeliveryLineItems.
        # If returnCreate gave us a reverseFulfillmentOrder but no line items, we cannot
        # attach tracking — surface it rather than firing a mutation Shopify will reject.
        if not reverse_delivery_line_items:
            return False, _(
                'Shopify returned no reverse-delivery line items to ship against.'
            )

        # ReverseDeliveryTrackingInput accepts only number + url (no carrier-name field), so
        # the carrier is conveyed via the tracking url — no carrier-code resolution needed.
        try:
            integration.adapter.attach_tracking_to_return(
                external_order_id=sale_order.external_order_name,
                reverse_fulfillment_order_id=reverse_fulfillment_order_gid,
                reverse_delivery_line_items=reverse_delivery_line_items,
                tracking_number=self.carrier_tracking_ref,
                tracking_url=self.carrier_tracking_url_prop or '',
            )
        except Exception as ex:  # noqa: BLE001 — best-effort
            _logger.warning(
                'Return export: tracking attachment failed for picking %s: %s',
                self.name, ex,
            )
            return False, str(ex)

        return True, ''

    def _log_return_export_to_chatter(self, external_return, tracking_ok, tracking_error):
        """Post a chatter message recording the export outcome and who initiated it."""
        self.ensure_one()
        parts = [
            _('Return exported to Shopify by %(user)s.', user=self.env.user.name),
            _('Shopify Return: %(gid)s', gid=external_return.external_str_id),
        ]
        if self.carrier_tracking_ref:
            if tracking_ok:
                parts.append(_('Tracking attached: %(num)s', num=self.carrier_tracking_ref))
            else:
                # The return itself was created in Shopify; only tracking failed. A
                # re-export is blocked by the duplicate guard (E520), so the only recourse
                # is to add the tracking directly in the Shopify admin — do NOT advise
                # re-exporting (it would just raise E520).
                parts.append(_(
                    'Tracking attachment failed: %(err)s. The return was created in '
                    'Shopify; add the tracking number directly in the Shopify admin.',
                    err=tracking_error,
                ))
        self.message_post(body='\n'.join(parts))
