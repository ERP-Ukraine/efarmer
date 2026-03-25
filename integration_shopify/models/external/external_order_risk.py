# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderRisk(models.Model):
    _name = 'external.order.risk'
    _description = 'External Order Risk'

    message = fields.Char(
        string='Risk Description',
        help='Detailed description of the identified risk factor',
    )
    sentiment = fields.Selection(
        selection=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
        ],
        string='Sentiment',
        help='Sentiment of this individual risk factor as assessed by Shopify',
    )
    risk_level = fields.Selection(
        selection=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('pending', 'Pending'),
            ('none', 'None'),
        ],
        string='Risk Level',
        help='Overall risk level of the assessment this factor belongs to',
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
            ('none', 'No Recommendation (Pending or No Risk)'),
        ]

    def _prepare_vals_from_external(self, data) -> dict:
        return dict(
            sentiment=(data.get('sentiment') or '').lower() or False,
            risk_level=(data.get('riskLevel') or '').lower() or False,
            message=data.get('description'),
            recommendation=data.get('recommendation', ''),
            external_order_str_id=str(data['order_id']),
        )
