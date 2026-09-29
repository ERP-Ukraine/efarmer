# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_sale_order_sub_status_bulk_wizard')
class TestIntegrationSaleOrderSubStatusBulkWizard(OdooIntegrationInit):
    """The bulk wizard writes a single invoice_journal_id onto every selected sub-status.
    Order statuses are a per-store concept (their meaning, and the automation that should
    run for them, is defined per e-commerce store), so mixing sub-statuses from different
    stores in one wizard — even stores that happen to share a company — is rejected."""

    def setUp(self):
        super().setUp()

        self.other_integration_same_company = self.env['sale.integration'].create({
            'name': 'Bulk Wizard Second Store (Same Company)',
            'type_api': 'no_api',
            'company_id': self.company_id_1.id,
        })

        self.sub_status_integration_1 = self.env['integration.sale.order.sub.status.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'bulk-wizard-test-status-1',
            'name': 'Bulk Wizard Test Status 1',
        })
        self.sub_status_integration_2 = self.env['integration.sale.order.sub.status.external'].create({
            'integration_id': self.integration_no_api_2.id,
            'code': 'bulk-wizard-test-status-2',
            'name': 'Bulk Wizard Test Status 2',
        })
        self.sub_status_other_integration_same_company = self.env[
            'integration.sale.order.sub.status.external'
        ].create({
            'integration_id': self.other_integration_same_company.id,
            'code': 'bulk-wizard-test-status-1-other-store',
            'name': 'Bulk Wizard Test Status 1 (Other Store, Same Company)',
        })

    def test_single_integration_sub_statuses_allowed(self):
        """Selecting sub-statuses from one store only is fine, and company_id
        resolves to that store's company."""
        another_status = self.env['integration.sale.order.sub.status.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'bulk-wizard-test-status-1b',
            'name': 'Bulk Wizard Test Status 1b',
        })
        wizard = self.env['integration.sale.order.sub.status.bulk.wizard'].create({
            'sub_status_ids': [(6, 0, (self.sub_status_integration_1 | another_status).ids)],
        })
        self.assertEqual(wizard.company_id, self.company_id_1)

    def test_mixed_integration_sub_statuses_raises(self):
        """Selecting sub-statuses from two different stores must be rejected,
        even across companies."""
        with self.assertRaises(ValidationError):
            self.env['integration.sale.order.sub.status.bulk.wizard'].create({
                'sub_status_ids': [(6, 0, (
                    self.sub_status_integration_1 | self.sub_status_integration_2
                ).ids)],
            })

    def test_mixed_integration_same_company_sub_statuses_raises(self):
        """Two stores sharing the same company are still two different stores —
        the constraint is per-store, not per-company, so this is rejected too."""
        with self.assertRaises(ValidationError):
            self.env['integration.sale.order.sub.status.bulk.wizard'].create({
                'sub_status_ids': [(6, 0, (
                    self.sub_status_integration_1 | self.sub_status_other_integration_same_company
                ).ids)],
            })
