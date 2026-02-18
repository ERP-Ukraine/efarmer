# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class FulfillmentLineItem(GqlDict):

    _gid_name = 'FulfillmentLineItem'
    _body = GqlDict._tmpl.FULFILLMENT_LINE_ITEM_BODY

    @property
    def sale_line_item(self):
        self.ensure_one()
        return self._env.LineItem.set(**(self['lineItem'] or {}))

    @property
    def fulfillable_quantity(self):
        self.ensure_one()
        return self.quantity - self.sale_line_item.non_fulfillable_quantity

    def to_odoo_format(self):
        self.ensure_one()

        line_item = self.sale_line_item
        variant = line_item.variant

        return dict(
            external_str_id=line_item.id_str,  # Serialize OrderLine.ID for an external.order.fulfillment.line
            quantity=self.quantity,
            external_reference=line_item.sku,
            fulfillable_quantity=self.fulfillable_quantity,
            code=variant and variant.external_id or None,
        )
