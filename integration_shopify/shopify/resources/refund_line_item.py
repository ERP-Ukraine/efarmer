# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


RESTOCK_TYPE_MAP = {
    'NO_RESTOCK': 'no_restock',
    'RETURN': 'return',
    'CANCEL': 'cancel',
    'LEGACY_RESTOCK': 'legacy_restock',
}


class RefundLineItem(GqlDict):

    _gid_name = 'RefundLineItem'

    def __init__(self, *args, **kwargs):
        # Shopify's RefundLineItem GraphQL node carries no stable id of its own — the line is
        # identified by the underlying lineItem. Set a pseudo id so ensure_one() / __bool__
        # treat populated instances as singletons (same pattern as MoneyBag).
        super().__init__(*args, **kwargs)
        self._set_pseudo_id()

    @property
    def line_item(self):
        self.ensure_one()
        return self._env.LineItem.set(**(self['lineItem'] or {}))

    @property
    def location(self):
        self.ensure_one()
        return self._env.Location.set(**(self['location'] or {}))

    @property
    def price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['priceSet'] or {}))

    @property
    def subtotal_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['subtotalSet'] or {}))

    @property
    def total_tax_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['totalTaxSet'] or {}))

    @property
    def restock_type(self):
        self.ensure_one()
        return RESTOCK_TYPE_MAP.get(self['restockType'] or 'NO_RESTOCK', 'no_restock')

    def to_odoo_format(self, use_customer_currency=False):
        self.ensure_one()
        # external_line_str_id / external_location_str_id store the bare numeric id (id_str),
        # matching sale.order.line.integration_external_id so the resolution in the base flow
        # is a direct equality comparison (no GID/numeric tolerance needed).
        line_item = self.line_item
        location = self.location
        subtotal_set = self.subtotal_set
        return dict(
            external_line_str_id=line_item.id_str,
            quantity=self['quantity'] or 0,
            restock_type=self.restock_type,
            external_location_str_id=location.id_str if location['id'] else '',
            original_unit_price=self.price_set.get_amount(use_customer_currency),
            subtotal=subtotal_set.get_amount(use_customer_currency),
            total_tax=self.total_tax_set.get_amount(use_customer_currency),
            currency_code=subtotal_set.get_currency(use_customer_currency),
            external_sku=line_item['sku'] or '',
        )

    def to_return_line_format(self, return_str_id):
        """Serialize this refund line as a return line for a synthesized return.

        Used for Shopify's legacy refund-driven restock: the order-level "Refund"
        action with restock produces a refund line carrying restockType=RETURN but
        no separate Return entity. We mirror the WooCommerce pattern (_map_refund)
        and emit a return line so the standard return pipeline creates the restock
        picking. external_line_str_id stores the bare numeric LineItem id (matched directly
        against the numeric SO-line id); external_fulfillment_str_id is left empty so the
        base flow uses the single-picking fallback (the refund line references the LineItem,
        not the FulfillmentLineItem).
        """
        self.ensure_one()
        line_item = self.line_item
        return dict(
            external_str_id='%s/%s' % (return_str_id, line_item.id_str),
            external_line_str_id=line_item.id_str,
            quantity=self['quantity'] or 0,
            external_sku=line_item['sku'] or '',
            external_fulfillment_str_id='',
        )
