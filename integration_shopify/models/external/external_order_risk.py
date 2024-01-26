# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderRisk(models.Model):
    _name = 'external.order.risk'
    _description = 'External Order Risk'

    message = fields.Char(
        string='Message',
    )
    score = fields.Char(
        string='Score',
        help='A number between 0 and 1 that\'s assigned to the order. '
             'The closer the score is to 1, the more likely it is that the order is fraudulent.',
    )
    source = fields.Char(
        string='Risk Source',
        help='The source of the order risk.',
    )
    external_str_id = fields.Char(
        string='External ID',
    )
    external_order_str_id = fields.Char(
        string='External Order ID',
    )
    erp_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='ERP Order',
        ondelete='cascade',
    )
    recommendation = fields.Selection(
        selection=lambda self: self._select_recommendation(),
        string='Recommendation',
        default='accept',
        help="""
            cancel: There is a high level of risk that this order is fraudulent.
                    The merchant should cancel the order.

            investigate: There is a medium level of risk that this order is fraudulent.
                         The merchant should investigate the order.

            accept: There is a low level of risk that this order is fraudulent.
                    The order risk found no indication of fraud.
        """
    )

    def _select_recommendation(self):
        return [
            ('cancel', 'High level of risk'),
            ('investigate', 'Medium level of risk'),
            ('accept', 'Low level of risk'),
        ]

    def _create_or_update_risk_from_external(self, data):
        record = self.search([
            ('external_str_id', '=', str(data['id'])),
            ('external_order_str_id', '=', str(data['order_id'])),
        ], limit=1)

        vals = self._prepare_vals_from_external(data)

        if not record:
            record = self.create(vals)
        else:
            record.write(vals)

        return record

    def _prepare_vals_from_external(self, data):
        vals = dict(
            score=data['score'],
            source=data['source'],
            message=data['message'],
            external_str_id=str(data['id']),
            recommendation=data['recommendation'],
            external_order_str_id=str(data['order_id']),
        )
        return vals
