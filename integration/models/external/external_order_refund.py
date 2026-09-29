# See LICENSE file for full copyright and licensing details.

import logging
from copy import deepcopy
from datetime import timezone

from dateutil import parser as date_parser

from odoo import models, fields, api, _
from odoo.tools import float_round, formatLang

from ...exceptions import ErrorStore as es


_logger = logging.getLogger(__name__)


class ExternalOrderRefund(models.Model):
    _name = 'external.order.refund'
    _inherit = 'external.order.resource'
    _description = 'External Order Refund'

    total_refunded_amount = fields.Monetary(
        string='Total Refunded Amount',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
    )
    note = fields.Char(
        string='Refund Reason',
        help='Free text refund reason from merchant',
    )
    created_at_external = fields.Datetime(
        string='Created At (External)',
    )
    linked_return_str_id = fields.Char(
        string='Linked Return External ID',
        help='From Refund.return.id if present',
    )
    linked_return_id = fields.Many2one(
        comodel_name='external.order.return',
        string='Linked Return',
        help='Return record linked to this refund (placeholder refund pattern). '
             'Resolved from linked_return_str_id during ingestion.',
    )
    parent_refund_str_id = fields.Char(
        string='Parent Refund ID',
        help='Reserved for future chain support; unused in v1',
    )
    line_ids = fields.One2many(
        comodel_name='external.order.refund.line',
        inverse_name='refund_id',
        string='Refund Lines',
    )
    data_hash = fields.Char(
        string='Data Hash',
    )
    external_timestamp = fields.Datetime(
        string='External Timestamp',
    )
    credit_note_id = fields.Many2one(
        comodel_name='account.move',
        string='Credit Note',
        help='Posted credit note in Odoo',
    )
    transaction_ids = fields.One2many(
        comodel_name='external.order.transaction',
        inverse_name='external_refund_id',
        string='Refund Transactions',
        help='External transactions (kind=REFUND) linked to this refund.',
    )
    payment_ids = fields.Many2many(
        comodel_name='account.payment',
        string='Refund Payments',
        help='Refund payments registered',
    )
    is_placeholder = fields.Boolean(
        string='Is Placeholder',
        compute='_compute_is_placeholder',
        store=True,
        help='True when total_refunded_amount == 0 and a linked return exists',
    )

    @api.depends('total_refunded_amount', 'linked_return_id')
    def _compute_is_placeholder(self):
        for rec in self:
            rec.is_placeholder = (
                rec.total_refunded_amount == 0
                and bool(rec.linked_return_id)
            )

    def _compute_is_ecommerce_ok(self):
        """A refund is processable when it has a non-zero amount or a linked return."""
        for rec in self:
            rec.is_ecommerce_ok = bool(rec.total_refunded_amount) or bool(rec.linked_return_id)

    def _prepare_vals_from_external(self, data: dict) -> dict:
        vals = deepcopy(data)

        # Convert nested line dicts into ORM commands
        lines = vals.pop('lines', [])
        # Resolve currency_code on each line before wrapping in ORM commands. active_test=False:
        for line in lines:
            currency_code = line.pop('currency_code', None)
            if currency_code:
                currency = self.env['res.currency'].with_context(active_test=False).search([
                    ('name', '=', currency_code),
                ], limit=1)
                if currency:
                    line['currency_id'] = currency.id
        vals['line_ids'] = [(5,)] + [(0, 0, x) for x in lines]

        # Resolve currency_code on the refund itself. active_test=False
        currency_code = vals.pop('currency_code', None)
        if currency_code:
            currency = self.env['res.currency'].with_context(active_test=False).search([
                ('name', '=', currency_code),
            ], limit=1)
            if currency:
                vals['currency_id'] = currency.id

        # Convert ISO 8601 datetime (Shopify sends e.g. "2026-05-01T11:40:21Z") to Odoo's
        # naive-UTC storage format. isoparse handles both the trailing-Z form and explicit
        # offsets; we normalise to UTC before dropping tzinfo so any future non-Z source still
        # stores the right wall-clock value.
        if vals.get('created_at_external'):
            try:
                dt = date_parser.isoparse(vals['created_at_external'])
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                vals['created_at_external'] = fields.Datetime.to_string(dt)
            except (ValueError, TypeError):
                vals.pop('created_at_external', None)

        # Resolve the refund's transaction ids to existing external.order.transaction records.
        # Setting them on transaction_ids writes the M2O external_refund_id on each transaction
        # via the One2many inverse, which is what _register_refund_payment relies on to mark
        # refund-kind transactions as done — otherwise they are left stuck in Draft on the
        # dashboard. Both sides store the connector's bare external id (numeric), so the lookup
        # is a direct match. The order entity pipeline creates transactions before refunds, so
        # the records exist when this runs.
        transaction_str_ids = vals.pop('transaction_str_ids', None)
        if transaction_str_ids:
            integration_id = self.env.context.get('integration_id')
            txns = self.env['external.order.transaction'].search([
                ('external_str_id', 'in', transaction_str_ids),
                ('integration_id', '=', integration_id),
            ])
            if txns:
                vals['transaction_ids'] = [(6, 0, txns.ids)]

        # Resolve the linked external.order.return GID to its record ID. Returns
        # are ingested before refunds in sale_order._apply_values_from_external, so
        # the record always exists when this runs.
        linked_return_str_id = vals.get('linked_return_str_id')
        if linked_return_str_id:
            integration_id = self.env.context.get('integration_id')
            ret = self.env['external.order.return'].search([
                ('external_str_id', '=', linked_return_str_id),
                ('integration_id', '=', integration_id),
            ], limit=1)
            if ret:
                vals['linked_return_id'] = ret.id

        return vals

    def _get_or_create_from_external(self, data):
        record = super()._get_or_create_from_external(data)
        # The transaction linkage (transaction_ids) is (re)resolved on every import. When a
        # REFUND-kind transaction links to a refund that was ALREADY processed, the refund
        # dispatch will not reprocess it (it filters out done refunds), so _register_refund_payment
        # never runs again to mark the transaction done. Reconcile here, at linkage time, so the
        # late-arriving transaction reflects the refund's processed state. No-op for unprocessed
        # refunds (gated on payment_ids inside the helper).
        record._reconcile_linked_transactions()
        return record

    def _validate(self):
        """Entry point for refund processing. Returns (bool, list)
        per parent class validate() contract.

        Distinguishes two failure modes:
        - PrerequisiteNotMet (soft fail): record stays in 'draft' for
          later retry when prerequisites are met (e.g. invoice not yet
          paid). Logged at INFO, not marked as failed.
        - UserError (hard fail): actual data/config error that won't
          auto-resolve. Record marked as failed, logged as warning.
        """
        self.ensure_one()

        # Terminal states: already processed, or intentionally skipped (a "refund later"
        # placeholder, or a merchant Skip). Return before touching internal_info so the
        # existing explanation is preserved and the record is not reprocessed. A skipped
        # record is still processed when the merchant forces it from the Apply button.
        was_skipped = self.internal_status == 'skipped'
        forced = self.env.context.get('integration_force_validate')

        if self.is_done or (was_skipped and not forced):
            return True, []

        # Drop the skip so the tail below can reach mark_done(). A placeholder re-skips
        # itself inside _process() and still ends up 'skipped'. Every failure path below
        # restores it — 'draft'/'failed' would put the record back into automatic dispatch.
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

        # _process() marks "refund later" placeholders as 'skipped' (with an explanatory
        # note). Don't overwrite that with 'done'.
        if self.internal_status != 'skipped':
            self.mark_done()
        return True, []

    def _process(self):
        """Dispatch refund processing based on amount / linked-return / restock_type."""
        self.ensure_one()
        has_amount = self.total_refunded_amount > 0
        has_linked_return = bool(self.linked_return_id)
        restock_types = set(self.line_ids.mapped('restock_type'))

        # Anomalous: a zero-amount refund only makes sense when paired with a return (the
        # "placeholder refund" pattern below). Without one, the platform data is inconsistent
        # and needs manual review.
        if not has_amount and not has_linked_return:
            es.raise_error(
                err_code='E513',
                err_msg=_(
                    'Refund %(code)s has zero amount and no linked return. '
                    'This is an anomalous state on the platform. Manual review required.',
                    code=self.external_str_id,
                ),
                support_contact=False,
            )

        # Placeholder refund — amount=0 with a linked return. Used by platforms (e.g.
        # Shopify's "process return now, refund later") to represent a return that has not yet
        # been refunded. No credit note or payment is needed: the linked return picking handles
        # the goods movement; the money refund arrives later as a separate non-zero refund.
        # Mark it 'skipped' (not 'done') and leave a plain-language note so a non-technical
        # user understands why the amount is 0 and there is no credit note.
        if not has_amount and has_linked_return:
            self.internal_info = _(
                'No credit note needed yet — this is a "refund later" placeholder. The store '
                'recorded the return now and will issue the money refund afterwards as a '
                'separate refund. The amounts shown on the lines describe the returned items; '
                'no money has moved yet. Odoo will create the credit note when the actual '
                'refund is imported.'
            )
            self.mark_skipped()
            return

        # Contradictory: CANCEL restock means "don't ship", but a linked return implies the
        # order was already shipped.
        if has_amount and has_linked_return and 'cancel' in restock_types:
            es.raise_error(
                err_code='E551',
                err_msg=_(
                    'Refund %(code)s has restock_type=CANCEL but the order is fulfilled. '
                    'CANCEL is meaningful only for unfulfilled orders. Manual review required.',
                    code=self.external_str_id,
                ),
                support_contact=False,
            )

        # Defensive guard for a connector parser gap. A refund whose lines say the goods were
        # restocked (RETURN / LEGACY_RESTOCK) should arrive paired with a return record that
        # owns the restock picking — the connector parser synthesizes one when the platform
        # doesn't (e.g. Shopify's legacy refund-driven restock, mirrored from WooCommerce). If
        # we reach here with a restock-return refund but no linked return, the parser failed to
        # synthesize it: the credit note below is still correct, but the restock picking is
        # missing. Warn loudly so the gap is visible rather than silently desyncing inventory.
        if has_amount and not has_linked_return and restock_types & {'return', 'legacy_restock'}:
            _logger.warning(
                'Refund %s restocks goods (restock types: %s) but has no linked return — the '
                'connector parser did not synthesize one. Credit note will be created, but no '
                'restock picking. Check the connector\'s refund parser.',
                self.external_str_id,
                ', '.join(sorted(restock_types & {'return', 'legacy_restock'})),
            )

        # Credit note + refund payment for any refund with amount > 0.
        self._create_credit_note()
        self._register_refund_payment(self.credit_note_id)

    def _create_credit_note(self):
        """Create a credit note for this refund via the account.move.reversal wizard."""
        self.ensure_one()

        # Idempotency: credit note already created for this refund. Logged at INFO and skipped
        # silently — this is a normal condition during retries or re-imports.
        if self.credit_note_id:
            _logger.info(
                'Refund %s already has linked credit note %s. Job skipped.',
                self.external_str_id,
                self.credit_note_id.name,
            )
            return

        order = self.erp_order_id

        original_invoice = self._resolve_original_invoice()

        # Currency mismatch must be caught BEFORE the reversal wizard runs. If we created the
        # credit note first and then discovered the mismatch, Odoo's account.move._post() would
        # auto-reconcile the new credit note with the original invoice's receivable line,
        # leaving an orphan posted credit note that requires manual cleanup.
        if self.currency_id and original_invoice.currency_id and self.currency_id != original_invoice.currency_id:
            es.raise_error(
                err_code='E506',
                err_msg=_(
                    'Cannot process refund %(code)s: refund currency %(ext_currency)s does not '
                    'match invoice currency %(odoo_currency)s. Manual intervention required.',
                    code=self.external_str_id,
                    ext_currency=self.currency_id.name,
                    odoo_currency=original_invoice.currency_id.name,
                ),
                support_contact=False,
            )

        # Detect manually-created credit notes on the order that aren't linked to any platform
        # refund — processing would risk double-crediting the customer.
        self._check_manual_credit_notes()

        # Verify all refund lines resolve to products on a posted invoice BEFORE creating the
        # reversal. Failing after reversal would leave an orphan credit note. Shipping lines are
        # skipped — they match the delivery line on the reversed invoice (handled in
        # _adjust_credit_note_lines), not a product by external id.
        for refund_line in self.line_ids.filtered(lambda ln: not ln.is_shipping):
            product = self._resolve_product_for_refund_line(refund_line)
            if not product:
                es.raise_error(
                    err_code='E501',
                    err_msg=_(
                        'Cannot process refund %(code)s: refunded line for product '
                        '%(product)s (SKU %(sku)s) is not on any posted invoice for '
                        'order %(order)s. The invoice(s) for this order may not cover '
                        'all sold lines yet. Post the invoice(s) covering the full '
                        'original order amount, then retry this job.',
                        code=self.external_str_id,
                        product=refund_line.external_sku or 'Unknown',
                        sku=refund_line.external_sku or '',
                        order=order.name,
                    ),
                    support_contact=False,
                )

        # Credit note date follows the external refund timestamp so historical imports reflect
        # when the refund actually occurred on the platform, not when the connector processed it.
        reversal_date = (
            self.created_at_external.date()
            if self.created_at_external
            else fields.Date.context_today(self)
        )
        move_reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move',
            active_ids=[original_invoice.id],
        ).create({
            'reason': self.note or '',
            'journal_id': original_invoice.journal_id.id,
            'date': reversal_date,
        })
        move_reversal.refund_moves()
        credit_note = move_reversal.new_move_ids

        if not credit_note:
            es.raise_error(
                err_code='E552',
                err_msg=_(
                    'Cannot process refund %(code)s: credit note creation via reversal wizard '
                    'returned no moves for order %(order)s.',
                    code=self.external_str_id,
                    order=order.name,
                ),
                support_contact=False,
            )

        credit_note = credit_note[0]

        # account.move.reversal builds the credit note via generic copy(), which skips
        # external_payment_method_id (copy=False, to avoid stale data on manual invoice
        # duplication) — carry it over explicitly so the credit note's E-Commerce
        # Integration tab shows the same payment method as the original invoice.
        credit_note.external_payment_method_id = original_invoice.external_payment_method_id

        # Modify reversal lines to match the refund. When the platform sent a flat refund amount
        # with no line breakdown (e.g. the lines were captured in a separate placeholder refund
        # earlier), replace all reversal lines with a single line for the total refund amount.
        if self.line_ids:
            self._adjust_credit_note_lines(credit_note, original_invoice)
        else:
            self._adjust_credit_note_lines_lineless(credit_note)

        # Reconcile any gap between the platform refund total and the credit note total
        # (merchant manually adjusted the refund amount). Runs before posting so the note's
        # total already matches the money refunded when the payment is registered against it.
        self._apply_refund_total_adjustment(credit_note)

        # Post the credit note. skip_external_entity_dispatch prevents action_post from
        # re-entering refund processing: without it, account_move._integration_post_invoice_post
        # would enqueue another processing job that sees credit_note_id not yet set on `self`
        # and falsely flags the credit note as a "manual" unlinked one.
        credit_note.with_context(
            skip_external_entity_dispatch=True,
        ).action_post()

        # Link back
        self.credit_note_id = credit_note

    def _resolve_original_invoice(self):
        """Find the posted, fully-paid invoice that covers all refunded lines."""
        self.ensure_one()
        order = self.erp_order_id
        all_invoices = order.invoice_ids.filtered(lambda m: m.state != 'cancel')

        # No invoice exists at all — soft fail, retried when an invoice is created and posted
        # by the lifecycle hook on invoice post.
        if not all_invoices:
            es.raise_error(
                err_code='E503',
                err_msg=_(
                    'Cannot process refund %(code)s: order %(order)s has no invoice. '
                    'Create and post an invoice for the full original order amount before '
                    'this refund can be processed. The refund will be applied as a credit note '
                    'against that invoice automatically. Options: (a) enable auto-workflow on '
                    'this integration so invoices are created automatically, (b) create the '
                    'invoice manually from the sale order via Create Invoice, then post it. '
                    'Will retry when invoice is posted.',
                    code=self.external_str_id,
                    order=order.name,
                ),
                support_contact=False,
            )

        posted_invoices = all_invoices.filtered(
            lambda m: m.state == 'posted' and m.move_type == 'out_invoice'
        )
        draft_invoices = all_invoices.filtered(
            lambda m: m.state == 'draft' and m.move_type == 'out_invoice'
        )

        # Invoice exists but is still in draft — soft fail, retried when the invoice is posted.
        if not posted_invoices and draft_invoices:
            inv = draft_invoices[0]
            es.raise_error(
                err_code='E502',
                err_msg=_(
                    'Cannot process refund %(code)s: order %(order)s has invoice %(invoice)s '
                    'in draft state. Post the invoice for the full original order amount '
                    '(not the refunded amount) before processing the refund. '
                    'Will retry when invoice is posted.',
                    code=self.external_str_id,
                    order=order.name,
                    invoice=inv.name,
                ),
                support_contact=False,
            )

        # No posted invoices (only canceled ones exist) — soft fail, retried when a fresh
        # invoice is created and posted.
        if not posted_invoices:
            es.raise_error(
                err_code='E503',
                err_msg=_(
                    'Cannot process refund %(code)s: order %(order)s has no invoice. '
                    'Create and post an invoice for the full original order amount before '
                    'this refund can be processed. The refund will be applied as a credit note '
                    'against that invoice automatically. Options: (a) enable auto-workflow on '
                    'this integration so invoices are created automatically, (b) create the '
                    'invoice manually from the sale order via Create Invoice, then post it. '
                    'Will retry when invoice is posted.',
                    code=self.external_str_id,
                    order=order.name,
                ),
                support_contact=False,
            )

        # Refund requires a fully-paid invoice. Odoo's account.move._post() auto-reconciles a
        # credit note with the original invoice when its receivable line is unreconciled
        # (unpaid) — that would silently consume the invoice balance instead of producing a
        # refundable credit note. On a paid invoice the receivable is already reconciled with
        # the payment, so the credit note stays outstanding for the refund payment step.
        #
        # Payment_state alone isn't reliable: it can read 'in_payment' while amount_residual is
        # still > 0 (e.g. a payment registered but its journal entry wasn't created because the
        # payment method's outstanding account isn't configured). currency_id.is_zero() checks
        # the actual residual, so that case falls into unpaid_posted_invoices below and gets the
        # ordinary "posted but not paid" E514 retry instead of silently passing as paid.
        paid_posted_invoices = posted_invoices.filtered(
            lambda m: m.payment_state in ('paid', 'in_payment')
            and m.currency_id.is_zero(m.amount_residual)
        )
        unpaid_posted_invoices = posted_invoices - paid_posted_invoices

        # Invoice posted but not paid — soft fail, retried when payment is registered
        # (lifecycle hook on invoice paid).
        if not paid_posted_invoices and unpaid_posted_invoices:
            inv = unpaid_posted_invoices[0]
            es.raise_error(
                err_code='E514',
                err_msg=_(
                    'Cannot process refund %(code)s: invoice %(invoice)s for order '
                    '%(order)s is posted but not paid (payment state: %(state)s). '
                    'A refund can only be processed against a paid invoice — otherwise '
                    "Odoo's auto-reconciliation on the credit note will silently consume "
                    "the invoice's outstanding balance instead of creating a refund payment. "
                    'The original payment must be registered first so that the invoice\'s '
                    'receivable line is reconciled. Note: "In Payment" status (waiting for '
                    'bank statement matching) is sufficient — full "Paid" is not required. '
                    'Will retry when payment is registered.',
                    code=self.external_str_id,
                    invoice=inv.name,
                    order=order.name,
                    state=inv.payment_state,
                ),
                support_contact=False,
            )

        # Find a paid posted invoice that covers all refunded product lines
        refund_products = set()
        for line in self.line_ids:
            product = self._resolve_product_for_refund_line(line)
            if product:
                refund_products.add(product.id)

        best_invoice = False
        for invoice in paid_posted_invoices.sorted('create_date', reverse=True):
            invoice_products = set(
                invoice.invoice_line_ids
                .filtered(lambda ln: ln.display_type == 'product')
                .mapped('product_id.id')
            )
            if refund_products <= invoice_products:
                best_invoice = invoice
                break

        if not best_invoice:
            # Build descriptive error with first missing product
            for line in self.line_ids:
                product = self._resolve_product_for_refund_line(line)
                if product and product.id not in set().union(
                    *(set(inv.invoice_line_ids.filtered(
                        lambda ln: ln.display_type == 'product'
                    ).mapped('product_id.id')) for inv in paid_posted_invoices)
                ):
                    es.raise_error(
                        err_code='E501',
                        err_msg=_(
                            'Cannot process refund %(code)s: refunded line for product '
                            '%(product)s (SKU %(sku)s) is not on any posted invoice for '
                            'order %(order)s. The invoice(s) for this order may not cover '
                            'all sold lines yet. Post the invoice(s) covering the full '
                            'original order amount, then retry this job.',
                            code=self.external_str_id,
                            product=product.name,
                            sku=line.external_sku or '',
                            order=order.name,
                        ),
                        support_contact=False,
                    )
            # Fallback if all products exist individually but no single invoice covers all
            es.raise_error(
                err_code='E501',
                err_msg=_(
                    'Cannot process refund %(code)s: refunded line for product '
                    '%(product)s (SKU %(sku)s) is not on any posted invoice for '
                    'order %(order)s. The invoice(s) for this order may not cover '
                    'all sold lines yet. Post the invoice(s) covering the full '
                    'original order amount, then retry this job.',
                    code=self.external_str_id,
                    product=self.line_ids[0].external_sku or 'Unknown',
                    sku=self.line_ids[0].external_sku or '',
                    order=order.name,
                ),
                support_contact=False,
            )

        return best_invoice

    def _resolve_product_for_refund_line(self, refund_line):
        """Resolve the Odoo product for a refund line.

        Matches refund_line.external_line_str_id to sale.order.line.integration_external_id
        on the parent order. Both store the connector's bare external id (numeric), so the
        comparison is direct equality. The product is already resolved on the SO line
        during order import.
        """
        if not refund_line.external_line_str_id:
            return False

        for so_line in self.erp_order_id.order_line:
            if not so_line.product_id:
                continue
            if so_line.integration_external_id == refund_line.external_line_str_id:
                return so_line.product_id

        return False

    def _adjust_credit_note_lines(self, credit_note, original_invoice):
        """Modify the wizard-created credit note lines to match the refund."""
        # Build a map of refund lines by product (shipping lines are matched separately, by the
        # delivery flag — they don't resolve to a product by external id).
        refund_line_map = {}
        for refund_line in self.line_ids.filtered(lambda ln: not ln.is_shipping):
            product = self._resolve_product_for_refund_line(refund_line)
            if product:
                refund_line_map[product.id] = refund_line

        # Aggregate the shipping refund. WC may send several shipping_lines but the reversed
        # invoice carries a single delivery line; the parser already aggregates, so this is a
        # defensive sum. Matched to the credit note's delivery line below (kept, not removed,
        # so the credit note total reflects the refunded shipping). Both connectors store the
        # shipping refund as a tax-EXCLUDED subtotal plus a separate tax amount.
        shipping_refund_lines = self.line_ids.filtered('is_shipping')
        shipping_refund_subtotal = sum(shipping_refund_lines.mapped('subtotal'))
        shipping_refund_tax = sum(shipping_refund_lines.mapped('total_tax'))

        # Process existing credit note lines
        lines_to_remove = self.env['account.move.line']
        lines_matched = set()

        for cn_line in credit_note.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
        ):
            # Delivery line: the reversal preserves sale_line_ids, so the credit note line for
            # shipping links back to the SO delivery line (is_delivery=True). Keep it and set
            # its price_unit to the refunded shipping. price_unit must match the line's tax
            # mode: for a price-included tax (e.g. EU/PL VAT) it is the GROSS amount
            # (subtotal + tax), since Odoo derives the net from a tax-inclusive price_unit;
            # for a price-excluded tax it is the net subtotal and the tax is added on top.
            if shipping_refund_lines and cn_line.sale_line_ids.filtered('is_delivery'):
                tax_included = any(cn_line.tax_ids.mapped('price_include'))
                price_unit = shipping_refund_subtotal
                if tax_included:
                    price_unit += shipping_refund_tax
                cn_line.write({
                    'quantity': 1,
                    'price_unit': price_unit,
                })
                continue

            product_id = cn_line.product_id.id
            if product_id in refund_line_map and product_id not in lines_matched:
                refund_line = refund_line_map[product_id]
                cn_line.write({
                    'quantity': refund_line.quantity,
                    'price_unit': refund_line.original_unit_price,
                })
                lines_matched.add(product_id)
            else:
                lines_to_remove |= cn_line

        # Remove unmatched product lines
        if lines_to_remove:
            credit_note.write({
                'invoice_line_ids': [(2, line.id) for line in lines_to_remove],
            })

        # Add discount lines where discount_for_refund > 0. The discount product is resolved
        # lazily — refunds without any discount lines don't need the integration to have one
        # configured.
        discount_product = None
        for refund_line in self.line_ids:
            if refund_line.discount_for_refund > 0:
                if discount_product is None:
                    discount_product = self._get_discount_product()
                # Find the taxes from the matching product line on the credit note
                product = self._resolve_product_for_refund_line(refund_line)
                tax_ids = []
                if product:
                    matching_cn_line = credit_note.invoice_line_ids.filtered(
                        lambda ln: ln.display_type == 'product'
                        and ln.product_id.id == product.id
                    )
                    if matching_cn_line:
                        tax_ids = matching_cn_line[0].tax_ids.ids

                credit_note.write({
                    'invoice_line_ids': [(0, 0, {
                        'product_id': discount_product.id,
                        'quantity': 1,
                        'price_unit': -refund_line.discount_for_refund,
                        'tax_ids': [(6, 0, tax_ids)],
                    })],
                })

    def _adjust_credit_note_lines_lineless(self, credit_note):
        """Handle a refund with an amount but no line-item breakdown.

        The platform provided a total refund amount without specifying which products/quantities
        are being refunded — typically when the line detail was captured in an earlier
        placeholder refund and this refund is just the flat monetary follow-up. Replace all
        reversal-generated lines with a single line using the integration's configured refund
        product.
        """
        integration = self.integration_id

        if not integration.refund_product_id:
            es.raise_error(
                err_code='E553',
                err_msg=_(
                    'Cannot process refund %(code)s: this refund has no line-item '
                    'breakdown from the platform and requires a Refund Product to '
                    'create the credit note. Set Refund Product in the integration\'s '
                    'Returns & Refunds tab, then retry this job.',
                    code=self.external_str_id,
                ),
                support_contact=False,
            )

        # Collect sale_line_ids from reversal lines before removing them. The new refund line
        # must reference at least one SO line so the credit note appears in
        # sale.order.invoice_ids.
        product_lines = credit_note.invoice_line_ids.filtered(
            lambda ln: ln.display_type == 'product'
        )
        so_line_ids = product_lines.mapped('sale_line_ids').ids

        # Remove all product lines from the reversal copy
        if product_lines:
            credit_note.write({
                'invoice_line_ids': [(2, ln.id) for ln in product_lines],
            })

        credit_note.write({
            'invoice_line_ids': [(0, 0, {
                'product_id': integration.refund_product_id.id,
                'name': 'Refund: %s' % (self.note or self.external_str_id),
                'quantity': 1,
                'price_unit': self.total_refunded_amount,
                'tax_ids': [(5, 0, 0)],
                'sale_line_ids': [(6, 0, so_line_ids)],
            })],
        })

    def _apply_refund_total_adjustment(self, credit_note):
        """Reconcile a mismatch between the platform refund total and its line items.

        Merchants can edit the refund amount on the platform so it no longer equals the sum
        of the refunded line items — e.g. refunding 20 for 29 worth of items (a goodwill
        discount / restocking fee retained), or refunding more than the items account for.
        The credit note built from the line items would then total a different amount than the
        money actually refunded, so the refund payment could never fully reconcile it, leaving
        the credit note stuck in Partial forever. Add one tax-free adjustment line that brings
        the credit note total to the money actually refunded, so the payment reconciles cleanly.

        WHY TWO DIFFERENT TOTALS ARE COMPARED (this is deliberate, not a workaround):

        We have to answer two separate questions, and each needs its own reference number.

        1. "Did the merchant really adjust the refund?" — decided below by comparing the
           platform's stated total against the SAME platform's line amounts. Both sides come
           from the platform, so the only thing this comparison can detect is a real merchant
           edit. It deliberately does NOT compare against Odoo's number, because Odoo recomputes
           tax from its own product/tax setup and can land a cent away from the platform even on
           a perfectly faithful refund. If detection used Odoo's total instead, that 1-cent tax
           rounding would look like a "mismatch" and we would either book a bogus 1-cent
           adjustment or, when no adjustment product is configured, fail the whole refund with
           E555. So: platform-vs-platform answers "is there an adjustment?".

        2. "By how much do we move the credit note?" — decided lower down using the credit
           note's own amount_total (Odoo's source of truth), so that after the adjustment the
           note total lands exactly on the money refunded and the payment reconciles to zero,
           whatever rounding Odoo applied.

        A line's gross money is always subtotal + total_tax, regardless of how the platform
        split it (net+tax for tax-excluded pricing, gross-inclusive otherwise) and including
        shipping lines, with any line discount already baked into subtotal. So a faithful
        refund has total_refunded_amount == Σ(subtotal + total_tax); a genuine adjustment is
        exactly when it does not.

        Tolerance mirrors the order-import total-difference correction (Product Price
        precision), not a hardcoded epsilon. Lineless refunds are skipped — they have no line
        items to sum and their single credit note line was already set to total_refunded_amount.
        """
        self.ensure_one()

        # Lineless refunds: handled by _adjust_credit_note_lines_lineless, which already set the
        # single credit note line to total_refunded_amount — nothing to reconcile, and no line
        # items to sum (summing zero lines would spuriously flag the whole total as a mismatch).
        if not self.line_ids:
            return

        precision = self.env['decimal.precision'].precision_get('Product Price')
        refund_total = self.total_refunded_amount
        currency = credit_note.currency_id

        # Question 1 — is this a genuine merchant adjustment? Compare the platform's refund
        # total against the platform's own line grosses (subtotal + tax per line). If they
        # agree, the refund faithfully reflects its line items: there is nothing to reconcile,
        # so bail out. Any cent of difference against Odoo's recomputed note total at this point
        # is just tax-rounding noise and must NOT trigger an adjustment (see the docstring).
        lines_total = sum(self.line_ids.mapped('subtotal')) + sum(self.line_ids.mapped('total_tax'))
        if not float_round(refund_total - lines_total, precision_digits=precision):
            return

        # Question 2 — by how much do we move the credit note? Size the adjustment against the
        # credit note's own amount_total so the note lands exactly on the money refunded. Signed:
        # negative when the items sum to MORE than the refund (reduces the note), positive when
        # they sum to LESS (increases it). Checked before the adjustment-product requirement:
        # if Odoo's recomputed note total already equals the refund total there is nothing to
        # book, so we must not fail over a missing product.
        difference = float_round(refund_total - credit_note.amount_total, precision_digits=precision)
        if not difference:
            return

        adjustment_product = self.integration_id.refund_adjustment_product_id
        if not adjustment_product:
            es.raise_error(
                err_code='E555',
                err_msg=_(
                    'Cannot process refund %(code)s: the refund total (%(total)s) does not '
                    'match the sum of the refunded items (%(lines)s). Difference: %(diff)s.\n\n'
                    'This usually means the refund amount was adjusted manually in the source '
                    'platform. To record the difference automatically, set a Refund Adjustment '
                    'Product on the integration\'s Returns & Refunds settings tab. Otherwise, '
                    'adjust the refund in the source platform so the amounts match, then retry '
                    'this job.',
                    code=self.external_str_id,
                    total=formatLang(self.env, refund_total, currency_obj=currency),
                    lines=formatLang(self.env, lines_total, currency_obj=currency),
                    diff=formatLang(self.env, abs(refund_total - lines_total), currency_obj=currency),
                ),
                support_contact=False,
            )

        # Tax-free — the adjustment is a pure monetary reconciliation, not a taxable supply.
        credit_note.write({
            'invoice_line_ids': [(0, 0, {
                'product_id': adjustment_product.id,
                'name': _('Refund adjustment'),
                'quantity': 1,
                'price_unit': difference,
                'tax_ids': [(5, 0, 0)],
            })],
        })

        credit_note.message_post(body=_(
            'Adjustment line added: the refund total (%(total)s) differs from the sum of the '
            'refunded line items (%(lines)s). The difference of %(diff)s was recorded using the '
            'Refund Adjustment Product (%(product)s).\n\n'
            'If the discrepancy is unexpected, review the refund in the platform to confirm the '
            'intended amounts. A common cause is a manually overridden refund total or manually '
            'edited tax amounts.',
            total=formatLang(self.env, refund_total, currency_obj=currency),
            lines=formatLang(self.env, lines_total, currency_obj=currency),
            diff=formatLang(self.env, refund_total - lines_total, currency_obj=currency),
            product=adjustment_product.display_name,
        ))

    def _check_manual_credit_notes(self):
        """Reject processing when the order already has credit note(s) not linked
        to any platform refund — processing would risk double-crediting the
        customer.
        """
        self.ensure_one()
        order = self.erp_order_id
        credit_notes_on_order = order.invoice_ids.filtered(
            lambda m: m.move_type == 'out_refund' and m.state != 'cancel'
        )
        if not credit_notes_on_order:
            return

        # Find credit notes linked to any external.order.refund
        linked_cn_ids = set(
            self.env['external.order.refund'].search([
                ('credit_note_id', '!=', False),
            ]).mapped('credit_note_id.id')
        )

        unlinked = credit_notes_on_order.filtered(lambda m: m.id not in linked_cn_ids)
        if unlinked:
            cn_names = ', '.join(n or 'Draft' for n in unlinked.mapped('name'))
            es.raise_error(
                err_code='E509',
                err_msg=_(
                    'Cannot process refund %(code)s: order %(order)s has manual credit note(s) '
                    '%(cn_names)s not linked to any platform refund. To prevent double crediting, '
                    'link or cancel these manually, then retry.',
                    code=self.external_str_id,
                    order=order.name,
                    cn_names=cn_names,
                ),
                support_contact=False,
            )

    def _get_refund_journal(self):
        """Resolve the journal for the refund payment from the order's payment method.

        Refunds always flow back through the original payment method
        (matches platform behavior such as Shopify's locked "Original
        payment" refund method). Fails-loud when the order's payment
        method has no journal mapping — there is no fallback by design.
        """
        self.ensure_one()
        order = self.erp_order_id

        if order.payment_method_id:
            external_pm = order.payment_method_id.to_external_record(self.integration_id)
            if external_pm and external_pm.payment_journal_id:
                return external_pm.payment_journal_id

        method_name = order.payment_method_id.name if order.payment_method_id else '(none)'
        es.raise_error(
            err_code='E504',
            err_msg=_(
                'Cannot process refund %(code)s: no refund journal available. '
                'Configure a Payment Journal on the order\'s payment method '
                '"%(method)s" (Configuration → Payment Methods).',
                code=self.external_str_id,
                method=method_name,
            ),
            support_contact=False,
        )

    def _register_refund_payment(self, credit_note):
        """Register a refund payment against the credit note via the
        account.payment.register wizard. The payment journal is resolved by
        _get_refund_journal() — see that method for the resolution rule.
        """
        self.ensure_one()

        # Idempotency: payment already registered for this refund. Still reconcile the linked
        # REFUND-kind transactions before returning — the payment may have been registered on a
        # previous run while the transaction linkage only resolved later, in which case the
        # transactions would otherwise stay in Draft.
        if self.payment_ids:
            _logger.info(
                'Refund %s already has linked payments. Skipping payment registration.',
                self.external_str_id,
            )
            self._reconcile_linked_transactions()
            return

        integration = self.integration_id
        refund_journal = self._get_refund_journal()

        # Similar to _get_refund_journal
        external_payment_method = self.erp_order_id.payment_method_id.to_external_record(integration)
        payment_method_line = external_payment_method.payment_method_line_id if external_payment_method else False
        if payment_method_line:
            self = self.with_context(default_payment_method_line_id=payment_method_line.id)

        # Payment date follows the external refund timestamp so it matches
        # the credit note date for consistent accounting.
        payment_date = (
            self.created_at_external.date()
            if self.created_at_external
            else fields.Date.context_today(self)
        )

        # skip_external_entity_dispatch prevents the invoice-paid hook from
        # re-entering external-entities processing while we are still mid-flight here.
        # If the payment fully reconciles the credit note (e.g. lineless refund where
        # total_refunded_amount equals the credit-note total exactly), the credit note
        # transitions to paid and would otherwise enqueue a synchronous dispatch in
        # queue_job__no_delay test contexts — that dispatch would find self.payment_ids
        # still empty (assigned below) and attempt a second payment registration, which
        # then fails with "nothing left to pay". The context propagates through the
        # wizard env to the eventual _enqueue_external_entities_processing guard.
        wizard = self.env['account.payment.register'].with_context(
            active_ids=credit_note.ids,
            active_model='account.move',
            default_integration_id=integration.id,
            skip_external_entity_dispatch=True,
        ).create({
            'amount': self.total_refunded_amount,
            'journal_id': refund_journal.id,
            'payment_date': payment_date,
            'communication': 'Refund of %s: %s' % (credit_note.name, self.note or ''),
            'payment_difference_handling': 'open',
        })

        payments = wizard._create_payments()

        # Link payments
        self.payment_ids = [(4, p.id) for p in payments]

        # Reflect the refund's processed state onto its linked REFUND-kind transactions.
        self._reconcile_linked_transactions()

    def _reconcile_linked_transactions(self):
        """Mark this refund's linked REFUND-kind transactions as done and attach the refund
        payments to them.

        Decoupled from payment *creation* on purpose: a refund transaction must end up 'done'
        whenever its refund has been processed (money moved), regardless of whether the payment
        was registered on this run or an earlier one, and regardless of when the transaction
        linkage resolved. Refund transactions are reconciled here rather than by the regular
        payment flow because they have no unpaid invoice to pay against; without this they sit
        in 'draft' forever and confuse the dashboard.

        Gated on payment_ids so it is a no-op for unprocessed refunds (still draft) and for
        zero-amount placeholder refunds (skipped, no payment). Idempotent — the (4, id) link
        commands and the is_done guard make repeated calls safe, so it can run on every import.
        """
        self.ensure_one()
        if not self.payment_ids:
            return
        for txn in self.transaction_ids.filtered(lambda t: not t.is_done):
            txn.payment_ids = [(4, p.id) for p in self.payment_ids]
            txn.mark_done()

    def _get_discount_product(self):
        """Return the product used on credit note discount lines.

        Uses the integration-level Discount Product (same product used for order-level
        discounts), so that refund discount lines and original-order discount lines
        share a single, configurable product. Fails-loud when the integration has none
        configured — refund processing should not silently invent products.
        """
        self.ensure_one()
        product = self.integration_id.discount_product_id
        if not product:
            es.raise_error(
                err_code='E554',
                err_msg=_(
                    'Cannot process refund %(code)s: integration "%(integration)s" has no '
                    'Discount Product configured. Go to E-Commerce Integrations → '
                    '%(integration)s → Sales Orders tab and set the Discount Product field.',
                    code=self.external_str_id,
                    integration=self.integration_id.name,
                ),
                support_contact=False,
            )
        return product

    def cancel_in_ecommerce_system(self):
        raise NotImplementedError
