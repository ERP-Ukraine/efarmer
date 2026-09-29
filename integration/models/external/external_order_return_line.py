# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderReturnLine(models.Model):
    _name = 'external.order.return.line'
    _description = 'External Order Return Line'

    return_id = fields.Many2one(
        comodel_name='external.order.return',
        string='Return',
        ondelete='cascade',
        required=True,
    )
    external_str_id = fields.Char(
        string='External Line ID',
    )
    external_line_str_id = fields.Char(
        string='Source Line ID',
        help='Source line ID (fulfillmentLineItem.lineItem.id)',
    )
    quantity = fields.Float(
        string='Requested Quantity',
    )
    refundable_qty = fields.Float(
        string='Refundable Quantity',
    )
    refunded_qty = fields.Float(
        string='Refunded Quantity',
    )
    return_reason = fields.Char(
        string='Return Reason',
        help='Human-friendly return reason as shown on the platform '
             '(e.g. "Customer changed their mind", "Damaged or defective"). '
             'Connectors map their platform reason code to this label.',
    )
    return_reason_note = fields.Char(
        string='Reason Note',
        help='Free text from customer',
    )
    external_sku = fields.Char(
        string='External SKU',
        help='For diagnostics',
    )
    external_fulfillment_str_id = fields.Char(
        string='Source Fulfillment ID',
        help='The Shopify Fulfillment ID this return line originated from. '
             'Used by multi-picking partition logic to determine which outgoing '
             'picking this return should be created against.',
    )
