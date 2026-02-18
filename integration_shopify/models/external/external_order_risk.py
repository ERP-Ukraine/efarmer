# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderRisk(models.Model):
    _name = 'external.order.risk'
    _description = 'External Order Risk'

    message = fields.Char(
        string='Risk Description',
        help='Detailed description of the identified risk or fraud indicator',
    )
    score = fields.Char(
        string='Risk Score',
        help='Risk assessment score between 0 and 1. Higher scores indicate greater fraud risk.',
    )
    source = fields.Char(
        string='Risk Source',
        help='Origin or system that identified this risk (e.g., Shopify Fraud Analysis, third-party service)',
    )
    external_str_id = fields.Char(
        string='External Risk ID',
        help='Unique identifier for this risk assessment in the external system',
    )
    external_order_str_id = fields.Char(
        string='External Order ID',
        help='Order identifier from the external e-commerce system',
    )
    erp_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sales Order',
        ondelete='cascade',
        help='Associated Odoo sales order',
    )
    recommendation = fields.Selection(
        selection=lambda self: self._select_recommendation(),
        string='Action Recommendation',
        default='accept',
        help="""
            Accept: Low risk - proceed with order fulfillment as normal
            Investigate: Medium risk - review order details before processing
            Cancel: High risk - cancel order due to suspected fraud
        """
    )

    def _select_recommendation(self):
        return [
            ('accept', 'Accept Order (Low Risk)'),
            ('investigate', 'Investigate Further (Medium Risk)'),
            ('cancel', 'Cancel Order (High Risk)'),
        ]

    def _create_or_update_risk_from_external(self, data):
        """
        Create or update a risk assessment record based on external data.

        Args:
            data (dict): External risk data from e-commerce platform

        Returns:
            record: Created or updated risk assessment record

        Note:
            Supports both legacy and current API formats for backward compatibility
        """
        if data.get('id'):
            # Legacy API format - search by external ID and order ID
            record = self.search([
                ('external_str_id', '=', str(data['id'])),
                ('external_order_str_id', '=', str(data['order_id'])),
            ], limit=1)
        else:
            # Current API format - search by order ID, score, and recommendation
            record = self.search([
                ('external_order_str_id', '=', str(data['order_id'])),
                ('score', '=', data['sentiment']),
                ('recommendation', '=', data['recommendation']),
            ], limit=1)

        vals = self._prepare_vals_from_external(data)

        if not record:
            record = self.create(vals)
        else:
            record.write(vals)

        return record

    def _prepare_vals_from_external(self, data) -> dict:
        """
        Prepare values for creating/updating risk assessment records

        Args:
            data (dict): Raw external risk data

        Returns:
            dict: Prepared values for Odoo record
        """
        vals = dict(
            score=data.get('score') or data.get('sentiment'),
            source=data.get('source') or '',
            message=data.get('message') or data.get('description'),
            external_str_id=str(data.get('id')) or '',
            recommendation=data['recommendation'],
            external_order_str_id=str(data['order_id']),
        )
        return vals
