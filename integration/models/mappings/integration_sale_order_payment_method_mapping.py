# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderPaymentMethodMapping(models.Model):
    _name = 'integration.sale.order.payment.method.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Sale Order Payment Method Mapping'
    _mapping_fields = ('payment_method_id', 'external_payment_method_id')

    payment_method_id = fields.Many2one(
        comodel_name='sale.order.payment.method',
        ondelete='cascade',
    )
    external_payment_method_id = fields.Many2one(
        comodel_name='integration.sale.order.payment.method.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_payment_method_id)',
            'Payment methods mapping should be unique per integration'
        ),
    ]
