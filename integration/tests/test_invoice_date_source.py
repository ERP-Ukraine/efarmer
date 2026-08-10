# See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install')
class TestInvoiceDateSource(OdooIntegrationInit):
    """Cover Invoice Date Source options for workflow invoice creation."""

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Invoice Date Test Partner'})
        self.invoice_journal = self.env['account.journal'].create({
            'name': 'Customer Invoices Invoice Date Test',
            'code': 'IDT',
            'type': 'sale',
            'company_id': self.company_id_1.id,
        })

        self.sub_status = self.env['integration.sale.order.sub.status.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'invoice-date-test-status',
            'name': 'Invoice Date Test Status',
            'create_invoice': True,
            'invoice_journal_id': self.invoice_journal.id,
            'invoice_date_source': 'order_date',
        })

        order_date = fields.Datetime.to_datetime('2024-01-15 12:00:00')
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'integration_id': self.integration_no_api_1.id,
            'company_id': self.company_id_1.id,
            'date_order': order_date,
            'order_line': [(0, 0, {
                'product_id': self.product_pp_1.id,
                'product_uom_qty': 1,
                'price_unit': 10,
            })],
        })
        self.pipeline = self.env['integration.workflow.pipeline'].create({
            'order_id': self.order.id,
            'sub_state_external_ids': [(6, 0, self.sub_status.ids)],
        })

    def _prepare_workflow_invoice_vals(self):
        return self.order.with_context(from_integration_workflow=True)._prepare_invoice()

    def test_order_date_uses_sales_order_date(self):
        self.sub_status.invoice_date_source = 'order_date'

        invoice_vals = self._prepare_workflow_invoice_vals()
        expected = fields.Date.context_today(self.order, self.order.date_order)

        self.assertEqual(self.pipeline.invoice_date_source, 'order_date')
        self.assertEqual(invoice_vals['invoice_date'], expected)

    def test_invoice_creation_date_uses_today(self):
        self.sub_status.invoice_date_source = 'invoice_creation_date'

        # Ensure the order date differs from "today" so the assertion is meaningful
        self.assertNotEqual(
            fields.Date.to_date(self.order.date_order),
            fields.Date.context_today(self.order),
        )

        invoice_vals = self._prepare_workflow_invoice_vals()
        expected = fields.Date.context_today(self.order)

        self.assertEqual(self.pipeline.invoice_date_source, 'invoice_creation_date')
        self.assertEqual(invoice_vals['invoice_date'], expected)

    def test_pipeline_defaults_to_order_date_without_sub_status(self):
        pipeline = self.env['integration.workflow.pipeline'].create({
            'order_id': self.order.id,
        })
        self.assertEqual(pipeline.invoice_date_source, 'order_date')
