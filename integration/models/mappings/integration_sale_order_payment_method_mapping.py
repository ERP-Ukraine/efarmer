# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderPaymentMethodMapping(models.Model):
    _name = 'integration.sale.order.payment.method.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Sale Order Payment Method Mapping'
    _mapping_fields = ('payment_method_id', 'external_payment_method_id')
    _mapping_label = 'Payment Method'

    payment_method_id = fields.Many2one(
        string='Odoo Payment Method',
        comodel_name='sale.order.payment.method',
        ondelete='cascade',
    )
    external_payment_method_id = fields.Many2one(
        string='External Payment Method',
        comodel_name='integration.sale.order.payment.method.external',
        required=True,
        ondelete='cascade',
    )

    _uniq_mapping = models.Constraint(
        'unique(integration_id, external_payment_method_id)',
        'Payment methods mapping should be unique per integration',
    )
