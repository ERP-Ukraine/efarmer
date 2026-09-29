# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..exceptions import ErrorStore as es


class IntegrationSaleOrderSubStatusBulkWizard(models.TransientModel):
    _name = 'integration.sale.order.sub.status.bulk.wizard'
    _inherit = 'integration.workflow.automation.mixin'
    _description = 'Order Status Automation Wizard'

    company_id = fields.Many2one(
        comodel_name='res.company',
        compute='_compute_company_id',
    )
    sub_status_ids = fields.Many2many(
        comodel_name='integration.sale.order.sub.status.external',
        relation='integration_sub_status_bulk_wizard_rel',
        string='Order Statuses',
    )
    is_single_status = fields.Boolean(
        compute='_compute_single_status_info',
    )
    single_status_name = fields.Char(
        compute='_compute_single_status_info',
    )

    @api.depends('sub_status_ids')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.sub_status_ids.company_id[:1]

    @api.constrains('sub_status_ids')
    def _check_single_integration(self):
        for rec in self.filtered(lambda r: len(r.sub_status_ids.integration_id) > 1):
            raise es.ValidationError(_(
                'The selected order statuses belong to different stores (%s). Configure automation for '
                'statuses from a single store at a time.'
            ) % ', '.join(rec.sub_status_ids.integration_id.mapped('name')))

    @api.depends('sub_status_ids')
    def _compute_single_status_info(self):
        for rec in self:
            single = len(rec.sub_status_ids) == 1
            rec.is_single_status = single
            rec.single_status_name = single and rec.sub_status_ids.name or False

    def action_apply(self):
        """Apply the configured automation steps to every selected order status."""
        self.ensure_one()

        if not self.sub_status_ids:
            raise UserError(_('No order statuses to update.'))

        self.sub_status_ids.write({
            'validate_order': self.validate_order,
            'apply_advance_payment': self.apply_advance_payment,
            'validate_picking': self.validate_picking,
            'create_invoice': self.create_invoice,
            'invoice_journal_id': self.invoice_journal_id.id,
            'invoice_date_source': self.invoice_date_source,
            'validate_invoice': self.validate_invoice,
            'send_invoice': self.send_invoice,
            'register_payment': self.register_payment,
        })

        return {'type': 'ir.actions.act_window_close'}
