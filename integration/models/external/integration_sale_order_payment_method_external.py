# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields


_logger = logging.getLogger(__name__)

INV_VALIDATED = 'validated'
INV_PAID = 'paid_in_payment'


class IntegrationSaleOrderPaymentMethodExternal(models.Model):
    _name = 'integration.sale.order.payment.method.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Sale Order Payment Method External'
    _odoo_model = 'sale.order.payment.method'

    payment_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Payment Journal',
        domain="[('type', 'in', ('cash', 'bank'))]",
    )
    payment_term_id = fields.Many2one(
        comodel_name='account.payment.term',
        string='Payment Terms',
        domain="[('company_id', 'in', [company_id, False])]",
    )
    send_payment_status_when = fields.Selection(
        selection=[
            (INV_PAID, 'Invoice marked as Paid/In Payment'),
            (INV_VALIDATED, 'Invoice is Validated'),
        ],
        string='Send payment status when',
        default=INV_PAID,
        required=True,
        help='Create Invoice in external system when in Odoo ...',
    )

    def unlink(self):
        # Delete all odoo payment methods also
        if not self.env.context.get('skip_other_delete', False):
            payment_mapping_model = self.mapping_model
            for external_payment_method in self:
                payment_method_mappings = payment_mapping_model.search([
                    ('external_payment_method_id', '=', external_payment_method.id)
                ])
                for mapping in payment_method_mappings:
                    mapping.payment_method_id.with_context(skip_other_delete=True).unlink()
        return super(IntegrationSaleOrderPaymentMethodExternal, self).unlink()

    def _fix_unmapped(self, adapter_external_data):
        # Payment methods should be pre-created automatically in Odoo
        payment_method_mapping_model = self.mapping_model
        unmapped_payment_methods = payment_method_mapping_model.search([
            ('integration_id', '=', self.integration_id.id),
            ('payment_method_id', '=', False),
        ])

        odoo_payment_method_model = self.env['sale.order.payment.method']

        for mapping in unmapped_payment_methods:
            odoo_payment_method = odoo_payment_method_model.search([
                ('name', '=', mapping.external_payment_method_id.name),
                ('integration_id', '=', mapping.external_payment_method_id.integration_id.id),
            ])

            if not odoo_payment_method:
                create_vals = {
                    'code': mapping.external_payment_method_id.external_reference,
                    'integration_id': mapping.external_payment_method_id.integration_id.id,
                    'name': mapping.external_payment_method_id.name,
                }
                odoo_payment_method = odoo_payment_method_model.create(create_vals)

            if len(odoo_payment_method) == 1:
                mapping.payment_method_id = odoo_payment_method.id
