# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.exceptions import UserError

from .config.integration_init import OdooIntegrationInit


class _StatusExported(UserError):
    """Sentinel raised by the patched dispatch so we can detect that a status export was queued."""


@tagged('post_install', '-at_install', 'test_integration_core')
class TestOrderStatusExport(OdooIntegrationInit):
    """The Shipped/Cancelled/Paid events push the order status to the store on their own toggle, via the
    `force_status_export` context honored by `SaleOrder.write()`. The master toggle
    (`export_sale_order_status_job_enabled`) governs only manual status changes.

    Exactly one export per REAL status change is guaranteed by write()'s before/after guard — not by queue_job's
    `identity_key`.
    """

    def setUp(self):
        super(TestOrderStatusExport, self).setUp()
        self.integration = self.integration_no_api_1
        self.partner = self.env['res.partner'].create({'name': 'SO Status Customer'})
        self.status_a = self.env['sale.order.sub.status'].create({
            'name': 'Status A', 'integration_id': self.integration.id,
        })
        self.status_b = self.env['sale.order.sub.status'].create({
            'name': 'Status B', 'integration_id': self.integration.id,
        })
        order = self.env['sale.order'].with_context(skip_dispatch_to_external=True).create({
            'partner_id': self.partner.id,
            'integration_id': self.integration.id,
            'sub_status_id': self.status_a.id,
        })
        # Re-browse for a clean context: the create-time `skip_dispatch_to_external` otherwise sticks to the handle
        # and would suppress every dispatch.
        self.order = self.env['sale.order'].browse(order.id)

        # Detect (without executing) a queued status export: with_delay returns the integration, and the patched
        # export raises a sentinel.
        def with_delay_patch(*args, **kw):
            return args[0]

        def export_status_patch(*args, **kw):
            raise _StatusExported('status-export-dispatched')

        self.patch(type(self.integration), 'with_delay', with_delay_patch)
        self.patch(type(self.integration), 'export_sale_order_status', export_status_patch)

    def _set_status(self, status, **ctx):
        self.order.with_context(**ctx).write({'sub_status_id': status.id})

    # An event (force_status_export) pushes even when the master toggle is OFF.
    def test_force_exports_when_master_off(self):
        self.integration.export_sale_order_status_job_enabled = False
        with self.assertRaises(_StatusExported):
            self._set_status(self.status_b, force_status_export=True)

    # A plain manual change does NOT push when the master toggle is OFF.
    def test_manual_no_export_when_master_off(self):
        self.integration.export_sale_order_status_job_enabled = False
        self._set_status(self.status_b)  # must NOT raise

    # A plain manual change pushes when the master toggle is ON.
    def test_manual_exports_when_master_on(self):
        self.integration.export_sale_order_status_job_enabled = True
        with self.assertRaises(_StatusExported):
            self._set_status(self.status_b)

    # Robustness: re-setting the SAME status pushes nothing (before/after guard), even with force.
    def test_same_status_no_export(self):
        self.integration.export_sale_order_status_job_enabled = True
        self._set_status(self.status_a, force_status_export=True)  # already Status A -> no change -> no raise

    # `skip_dispatch_to_external` always wins (used by webhook import to avoid echoing status back).
    def test_skip_dispatch_wins(self):
        self.integration.export_sale_order_status_job_enabled = True
        self._set_status(self.status_b, skip_dispatch_to_external=True, force_status_export=True)  # must NOT raise
