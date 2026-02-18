# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


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
        domain="[('type', 'in', ('cash', 'bank')), ('company_id', 'in', [company_id, False])]",
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

    @property
    def send_when_invoice_is_paid(self):
        self.ensure_one()
        return self.send_payment_status_when == INV_PAID

    @property
    def send_when_invoice_is_validated(self):
        self.ensure_one()
        return self.send_payment_status_when == INV_VALIDATED

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
        empty_mappings = self.mapping_model.search([
            ('integration_id', '=', self.integration_id.id),
            ('payment_method_id', '=', False),
        ])

        SaleOrderPaymentMethod = self.env['sale.order.payment.method']

        for mapping in empty_mappings:
            external_record = mapping.external_payment_method_id

            payment_method = SaleOrderPaymentMethod.search([
                ('name', '=', external_record.name),
                ('integration_id', '=', mapping.integration_id.id),
            ])

            if not payment_method:
                payment_method = SaleOrderPaymentMethod.create({
                    'name': external_record.name,
                    'code': external_record.external_reference,
                    'integration_id': mapping.integration_id.id,
                })

            if len(payment_method) == 1:
                mapping.payment_method_id = payment_method.id

    def _raise_for_missing_journal(self):
        self.ensure_one()

        if not self.payment_journal_id:
            raise UserError(_(
                '%s: No Payment Journal defined for Payment Method "%s". '
                'Please, define it in menu "E-Commerce Integrations → Configuration → '
                'Payment Methods" in the "Payment Journal" column.'
            ) % (self.integration_id.name, self.name))
