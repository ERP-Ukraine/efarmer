# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class Refund(GqlDict):

    _gid_name = 'Refund'
    _body = GqlDict._tmpl.ORDER_REFUND_BODY

    @property
    def total_refunded_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['totalRefundedSet'] or {}))

    @property
    def refund_line_items(self):
        self.ensure_one()
        return [self._env.RefundLineItem.set(**x) for x in (self['refundLineItems'] or [])]

    @property
    def transactions(self):
        self.ensure_one()
        return [self._env.OrderTransaction.set(**x) for x in (self['transactions'] or [])]

    @property
    def refund_shipping_lines(self):
        self.ensure_one()
        return [
            self._env.RefundShippingLine.set(**x)
            for x in (self['refundShippingLines'] or [])
        ]

    @property
    def linked_return(self):
        self.ensure_one()
        return self._env.Return.set(**(self['return'] or {}))

    @property
    def _restock_return_types(self):
        # restockType values that mean Shopify physically returned the goods.
        return ('return', 'legacy_restock')

    @property
    def synthesizes_return(self):
        """True when this refund implies a physical return that Shopify did not
        model as a separate Return entity.

        Shopify's order-level "Refund" action with "Restock" selected produces a
        refund whose lines carry restockType=RETURN (or the older LEGACY_RESTOCK)
        but leaves refund.return null and returns.edges empty. In that case we
        synthesize a return so the goods movement is tracked in Odoo. When a real
        Return entity exists (refund.return populated — the newer Returns API
        path), it takes precedence and nothing is synthesized.
        """
        self.ensure_one()
        if self.linked_return:
            return False
        return any(
            li.restock_type in self._restock_return_types
            for li in self.refund_line_items
        )

    @property
    def synthetic_return_str_id(self):
        """Stable external id for the synthesized return. The 'refund-' prefix
        marks it synthetic and guarantees it never collides with a real Shopify
        Return id (numeric) or a WooCommerce numeric refund id."""
        self.ensure_one()
        return 'refund-%s' % self.id_str

    def synthetic_return_format(self):
        """Build a return dict for the legacy refund-driven restock case, or None
        when this refund does not imply a return. Mirrors the WooCommerce pattern
        (WooOrder._map_refund): a paired return record is emitted alongside the
        refund so the standard return pipeline owns the restock picking. Only
        lines that actually restock (RETURN / LEGACY_RESTOCK) become return lines —
        NO_RESTOCK and CANCEL lines are skipped.
        """
        self.ensure_one()
        if not self.synthesizes_return:
            return None

        return_str_id = self.synthetic_return_str_id
        lines = [
            li.to_return_line_format(return_str_id)
            for li in self.refund_line_items
            if li.restock_type in self._restock_return_types
        ]
        return dict(
            external_str_id=return_str_id,
            # 'closed' (terminal): a refund-driven restock has no real Shopify Return
            # entity that could later change state, and the goods are already back in
            # sellable stock — the return is complete the moment it is synthesized. This
            # also keeps the record's state badge consistent with its processed status
            # instead of sitting on 'Open' forever.
            state='closed',
            # Shopify's restock means the goods are already back in sellable stock,
            # so the return picking is validated immediately on creation (the base
            # flow handles this via restocked_externally / the 'closed' state). Regular
            # returns leave it unset and their picking waits in Ready for physical receipt.
            restocked_externally=True,
            lines=lines,
        )

    def to_odoo_format(self, use_customer_currency=False):
        self.ensure_one()
        # external_str_id / linked_return_str_id / transaction_str_ids store the bare numeric
        # id (id_str), matching every other Shopify resource and the numeric SO line ids on
        # sale.order.line.integration_external_id — so all downstream resolution is a direct
        # equality comparison.
        total_set = self.total_refunded_set
        # Link to the real Return when Shopify modelled one; otherwise, for the legacy
        # refund-driven restock case, link to the synthesized return (see
        # synthetic_return_format) so the refund flow knows the goods movement is handled
        # by a return picking and the placeholder/zero-amount branches resolve correctly.
        linked_return = self.linked_return
        linked_return_str_id = linked_return.id_str if linked_return['id'] else ''
        if not linked_return_str_id and self.synthesizes_return:
            linked_return_str_id = self.synthetic_return_str_id

        lines = [x.to_odoo_format(use_customer_currency) for x in self.refund_line_items]
        shipping_line = self._shipping_refund_line(use_customer_currency)
        if shipping_line:
            lines.append(shipping_line)

        return dict(
            external_str_id=self.id_str,
            total_refunded_amount=total_set.get_amount(use_customer_currency),
            currency_code=total_set.get_currency(use_customer_currency),
            note=self['note'] or '',
            created_at_external=self['createdAt'] or False,
            linked_return_str_id=linked_return_str_id,
            lines=lines,
            # Numeric ids of the refund's kind=REFUND transactions. Resolved to existing
            # external.order.transaction records in the base _prepare_vals_from_external so the
            # transaction_ids One2many is populated and the dashboard doesn't leave them in Draft.
            transaction_str_ids=[txn.id_str for txn in self.transactions if txn['id']],
        )

    def _shipping_refund_line(self, use_customer_currency):
        """Aggregate the refund's shipping lines into one is_shipping refund line, or
        None when no shipping was refunded. Shopify exposes shipping refunds as a
        separate refundShippingLines connection (not as refundLineItems), so they are
        summed here and matched to the credit note delivery line by the base flow (by
        the is_delivery flag, not a product external id). Mirrors the WooCommerce
        shipping handling. subtotal is tax-excluded; the delivery line's own taxes
        recompute the tax on the credit note.
        """
        self.ensure_one()
        shipping_lines = self.refund_shipping_lines
        if not shipping_lines:
            return None

        subtotal = sum(
            s.subtotal_amount_set.get_amount(use_customer_currency) for s in shipping_lines
        )
        tax = sum(
            s.tax_amount_set.get_amount(use_customer_currency) for s in shipping_lines
        )
        if not subtotal and not tax:
            return None

        return dict(
            external_line_str_id='',
            quantity=1,
            restock_type='no_restock',
            external_location_str_id='',
            original_unit_price=subtotal,
            subtotal=subtotal,
            total_tax=tax,
            currency_code=self.total_refunded_set.get_currency(use_customer_currency),
            external_sku='',
            is_shipping=True,
        )
