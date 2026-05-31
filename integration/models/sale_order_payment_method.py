# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleOrderPaymentMethod(models.Model):
    _name = 'sale.order.payment.method'
    _description = 'Sale Order Payment Method'
    _inherit = ['integration.model.mixin']
    _internal_reference_field = 'code'

    name = fields.Char(
        string='Name',
        help='Here we will have user friendly name of the payment method',
        required=True,
    )

    code = fields.Char(
        string='Payment Method Code',
        help='In case it is possible - we will be able to insert here payment method code, '
             'to uniquely identify payment method',
    )

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        ondelete='cascade',
    )

    def unlink(self):
        # Delete all external payment methods also
        if not self.env.context.get('skip_other_delete', False):
            payment_mapping_model = self.env['integration.sale.order.payment.method.mapping']
            mappings = payment_mapping_model.search([('payment_method_id', 'in', self.ids)])
            mappings.mapped('external_payment_method_id').with_context(skip_other_delete=True).unlink()
        return super(SaleOrderPaymentMethod, self).unlink()
