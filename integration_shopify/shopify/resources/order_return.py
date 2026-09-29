# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


# Maps Shopify Return.status values to base external.order.return.state. Shopify's enum is
# OPEN, CLOSED, CANCELED, DECLINED, REQUESTED — we collapse REQUESTED into 'open' because both
# are actionable states the base flow treats identically (a picking still needs to be created).
RETURN_STATUS_MAP = {
    'OPEN': 'open',
    'CLOSED': 'closed',
    'CANCELED': 'canceled',
    'CANCELLED': 'canceled',  # tolerant of either spelling
    'DECLINED': 'declined',
    'REQUESTED': 'open',
}


class Return(GqlDict):

    _gid_name = 'Return'

    @property
    def return_line_items(self):
        self.ensure_one()
        return [self._env.ReturnLineItem.set(**x) for x in (self['returnLineItems'] or [])]

    @property
    def state(self):
        self.ensure_one()
        return RETURN_STATUS_MAP.get(self['status'] or '', 'open')

    def _extract_tracking(self):
        """First non-empty tracking from the first reverseDelivery.

        Known limitation: multi-package returns lose tracking from subsequent
        deliveries — only the first delivery's tracking is exposed to Odoo.
        """
        for rfo in (self['reverseFulfillmentOrders'] or []):
            for delivery in (rfo.get('reverseDeliveries') or []):
                tracking = (delivery.get('deliverable') or {}).get('tracking') or {}
                if tracking.get('number'):
                    return (
                        tracking.get('number') or '',
                        tracking.get('url') or '',
                        tracking.get('carrierName') or '',
                    )
        return '', '', ''

    def to_odoo_format(self, fulfillment_lookup=None):
        """Serialize one return into the base ORM dict shape.

        `fulfillment_lookup` is passed through to each ReturnLineItem so the
        base flow can create one return picking per parent fulfillment.
        """
        self.ensure_one()
        tracking_number, tracking_url, tracking_carrier = self._extract_tracking()
        line_dicts = [
            x.to_odoo_format(fulfillment_lookup) for x in self.return_line_items
        ]
        reasons = [d['return_reason'] for d in line_dicts if d['return_reason']]
        # external_str_id stores the bare numeric id (id_str), matching every other
        # Shopify resource and sale.order.line.integration_external_id. The wrapper
        # rebuilds the GID via create_gid() whenever the API is called.
        return dict(
            external_str_id=self.id_str,
            state=self.state,
            return_reason_summary=', '.join(reasons),
            reverse_tracking_number=tracking_number,
            reverse_tracking_url=tracking_url,
            reverse_tracking_carrier=tracking_carrier,
            lines=line_dicts,
        )
