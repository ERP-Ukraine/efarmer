# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _

from ..auto_workflow.integration_workflow_pipeline import (
    WORKFLOW_TASK_DEPENDENCIES,
    INVOICE_DATE_SOURCE_ORDER,
    INVOICE_DATE_SOURCE_CREATION,
)
from ...exceptions import ErrorStore as es
from ...tools import is_sale_advance_payment_installed


class IntegrationWorkflowAutomationMixin(models.AbstractModel):
    """Order-status automation steps, shared by the per-status config and the automation wizard."""

    _name = 'integration.workflow.automation.mixin'
    _description = 'Order Status Automation Steps'

    automation_steps_not_configured = fields.Boolean(
        string="No Selected Steps Chosen?",
        compute='_compute_automation_steps',
    )
    automation_steps_html = fields.Html(
        string='Automation Steps',
        compute='_compute_automation_steps',
        readonly=True,
    )
    validate_order = fields.Boolean(
        string='Confirm Sales Order',
        help='Automatically confirm the sales order when this status is reached',
    )
    validate_picking = fields.Boolean(
        string='Validate Delivery',
        help='Automatically validate the delivery when this status is reached',
    )
    create_invoice = fields.Boolean(
        string='Create Invoice',
        help='Automatically create a customer invoice when this status is reached',
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Invoice Journal',
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        help='Journal to use when creating invoices for this order status',
    )
    invoice_date_source = fields.Selection(
        selection=[
            (INVOICE_DATE_SOURCE_ORDER, 'Order Date'),
            (INVOICE_DATE_SOURCE_CREATION, 'Invoice Creation Date'),
        ],
        string='Default Invoice Date',
        help='Date assigned to invoices created by this workflow step. '
             '"Order Date" uses the sales order date (current behavior). '
             '"Invoice Creation Date" uses the date the invoice is created.',
    )
    validate_invoice = fields.Boolean(
        string='Confirm Invoice',
        help='Automatically confirm the invoice when this status is reached',
    )
    send_invoice = fields.Boolean(
        string='Send Invoice to Customer',
        help='Automatically send the invoice to the customer when this status is reached',
    )
    register_payment = fields.Boolean(
        string='Register Payment',
        help='Automatically register payment against the invoice when this status is reached',
    )
    apply_advance_payment = fields.Boolean(
        string='Register Advance Payment',
        help='Register the e-commerce payment on the order before invoicing, using the OCA '
             'module "sale_advance_payment". Seeded from the integration\'s "Create Advance '
             'Payments" setting when the step is first enabled, then editable per status.',
    )

    @staticmethod
    def _get_workflow_task_list():
        """Return the ordered list of workflow task field names.

        Override to add custom tasks; the order is critical for execution.
        """
        return list(WORKFLOW_TASK_DEPENDENCIES)

    @api.depends(*WORKFLOW_TASK_DEPENDENCIES)
    def _compute_automation_steps(self):
        for rec in self:
            steps = [
                rec._fields[task].string
                for task in rec._get_workflow_task_list()
                if getattr(rec, task)
            ]

            if not steps:
                rec.automation_steps_not_configured = True
                rec.automation_steps_html = '<span class="text-muted fst-italic">' + _('Not Configured') + '</span>'
                continue

            arrow = '<span class="text-muted mx-1">→</span>'
            steps_html = [
                f'<span class="d-inline-flex align-items-center gap-2 me-1">'
                f'<span class="text-bg-primary rounded-circle d-inline-flex align-items-center justify-content-center fw-bold" '  # NOQA
                f'style="width:1.5em;height:1.5em;font-size:.85em;line-height:1;">{i}</span>'
                f'<span>{name}</span>'
                f'</span>'
                for i, name in enumerate(steps, 1)
            ]

            rec.automation_steps_not_configured = False
            rec.automation_steps_html = (
                '<div class="d-flex flex-wrap align-items-center gap-1 my-2">'
                + arrow.join(steps_html)
                + '</div>'
            )

    def action_go_to_payment_methods(self):
        """Open the Payment Methods auto-workflow configuration in a new tab."""
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/eci-payment-methods-configuration',
            'target': 'new',
        }

    @api.constrains('apply_advance_payment')
    def _check_sale_advance_payment_module_installed(self):
        if not self.filtered('apply_advance_payment'):
            return

        if not is_sale_advance_payment_installed(self.env):
            raise es.ValidationError(_(
                'To enable "Register Advance Payment" you must first install the free OCA module '
                '"Sale Advance Payment".\n\nYou can find it on the OCA GitHub repository under "sale-workflow".'
            ))

    @api.constrains('apply_advance_payment', 'register_payment')
    def _check_single_payment_step(self):
        for rec in self.filtered(lambda r: r.apply_advance_payment and r.register_payment):
            raise es.ValidationError(_(
                '"%s": choose either "Register Advance Payment" or "Register Payment", not both — '
                'they register the same e-commerce payment at different points.', rec.display_name
            ))

    @api.onchange('validate_order')
    def _onchange_validate_order(self):
        """Reset dependent fields when order validation is disabled"""
        if not self.validate_order:
            self.apply_advance_payment = False
            self.validate_picking = False
            self.create_invoice = False
            self.invoice_journal_id = False
            self.invoice_date_source = False
            self.validate_invoice = False
            self.send_invoice = False
            self.register_payment = False

    @api.onchange('create_invoice')
    def _onchange_create_invoice(self):
        """Reset dependent fields when invoice creation is disabled"""
        if not self.create_invoice:
            self.invoice_journal_id = False
            self.invoice_date_source = False
            self.validate_invoice = False
            self.send_invoice = False
            self.register_payment = False

    @api.onchange('validate_invoice')
    def _onchange_validate_invoice(self):
        """Reset dependent fields when invoice validation is disabled"""
        if not self.validate_invoice:
            self.send_invoice = False
            self.register_payment = False

    @api.onchange('apply_advance_payment')
    def _onchange_apply_advance_payment(self):
        """Give instant feedback that the two payment steps are mutually exclusive"""
        if self.apply_advance_payment:
            self.register_payment = False

    @api.onchange('register_payment')
    def _onchange_register_payment(self):
        """Give instant feedback that the two payment steps are mutually exclusive"""
        if self.register_payment:
            self.apply_advance_payment = False
