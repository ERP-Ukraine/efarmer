# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


# Shopify ReturnReason enum → human-friendly label (the "Displays as" wording from
# Shopify's admin UI). Stored on return_reason so Odoo shows the same text the
# merchant sees in Shopify instead of the raw enum code (e.g. UNWANTED). Unknown /
# future values fall back to a prettified form of the code (see to_odoo_format).
RETURN_REASON_MAP = {
    'COLOR': 'Color',
    'DEFECTIVE': 'Damaged or defective',
    'NOT_AS_DESCRIBED': 'Item not as described',
    'OTHER': 'Other',
    'SIZE_TOO_LARGE': 'Size was too large',
    'SIZE_TOO_SMALL': 'Size was too small',
    'STYLE': 'Style',
    'UNKNOWN': 'Unknown',
    'UNWANTED': 'Customer changed their mind',
    'WRONG_ITEM': 'Received the wrong item',
}


class ReturnLineItem(GqlDict):

    _gid_name = 'ReturnLineItem'

    @property
    def fulfillment_line_item(self):
        self.ensure_one()
        return self._env.FulfillmentLineItem.set(**(self['fulfillmentLineItem'] or {}))

    @property
    def line_item(self):
        self.ensure_one()
        return self._env.LineItem.set(**(self.fulfillment_line_item['lineItem'] or {}))

    def to_odoo_format(self, fulfillment_lookup=None):
        """Serialize one return line into the base ORM dict shape.

        `fulfillment_lookup` maps FulfillmentLineItem GID → parent Fulfillment
        id_str (numeric). It is built once by Order.parse_returns() and passed
        down so the base flow can create one return picking per parent
        fulfillment (multi-picking partition). When the line's
        FulfillmentLineItem isn't in the lookup, the empty string triggers the
        single-picking fallback in the base flow.
        """
        self.ensure_one()
        # external_str_id / external_line_str_id store the bare numeric id (id_str), matching
        # every other Shopify resource and sale.order.line.integration_external_id.
        # external_fulfillment_str_id is likewise numeric (matches Fulfillment.to_odoo_format).
        line_item = self.line_item
        fli_gid = self.fulfillment_line_item['id'] or ''
        lookup = fulfillment_lookup or {}
        # Prefer the ReturnReasonDefinition label; returnReason is still requested and
        # used as a fallback, since Shopify can return a null definition (undocumented
        # legacy/custom reasons) even on 2026-07.
        definition = self['returnReasonDefinition'] or {}
        definition_name = definition.get('name') if isinstance(definition, dict) else ''
        raw_reason = self['returnReason'] or ''
        return_reason = (
            definition_name
            or RETURN_REASON_MAP.get(raw_reason, raw_reason.replace('_', ' ').capitalize())
        )

        return dict(
            external_str_id=self.id_str,
            external_line_str_id=line_item.id_str,
            quantity=self['quantity'] or 0,
            refundable_qty=self['refundableQuantity'] or 0,
            refunded_qty=self['refundedQuantity'] or 0,
            return_reason=return_reason,
            return_reason_note=self['returnReasonNote'] or '',
            external_sku=line_item['sku'] or '',
            external_fulfillment_str_id=lookup.get(fli_gid, ''),
        )
