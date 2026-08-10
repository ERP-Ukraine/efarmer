# See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo.addons.integration.exceptions import ApiImportError

from .config.integration_init import OdooIntegrationInit


class TestImportOrdersById(OdooIntegrationInit):
    """fetch_order_by_id()/import_orders() must always yield a recordset, never a bool.

    Regression: import_orders() does ``imported_orders |= fetch_order_by_id(...)``; when the
    order was not found or was skipped by the integration filter-rules, fetch_order_by_id()
    used to return ``False``, so the union crashed with
    ``TypeError: unsupported operand types in: sale.integration.input.file() | False``.
    """

    def _patch_adapter(self, integration, receive_order_return):
        adapter = MagicMock()
        adapter.receive_order.return_value = receive_order_return
        return patch.object(type(integration), '_build_adapter', return_value=adapter)

    def test_import_orders_no_crash_when_order_filtered_out(self):
        integration = self.integration_no_api_1
        model = type(integration)
        found_order = {'id': 'X', 'data': {}, 'updated_at': '2026-06-22T05:00:00Z'}

        with (
            self._patch_adapter(integration, found_order),
            patch.object(model, 'filter_received_orders', return_value=[]),  # skipped by rules
        ):
            result = integration.import_orders(external_ids=['X'])

        # No TypeError, and an (empty) recordset is returned.
        self.assertEqual(result, self.env['sale.integration.input.file'])

    def test_fetch_order_by_id_returns_recordset_when_not_found(self):
        integration = self.integration_no_api_1
        with self._patch_adapter(integration, None):  # not found
            result = integration.fetch_order_by_id('missing', raise_error=False)

        self.assertEqual(result, self.env['sale.integration.input.file'])
        self.assertFalse(result)  # empty recordset stays falsy for `if not result` callers

    def test_fetch_order_by_id_raises_when_not_found_and_raise_error(self):
        integration = self.integration_no_api_1
        with self._patch_adapter(integration, None), self.assertRaises(ApiImportError):
            integration.fetch_order_by_id('missing', raise_error=True)

    def test_fetch_order_by_id_returns_recordset_when_filtered_out(self):
        # A filtered-out order is a deliberate skip, not an error: it never raises (even with
        # raise_error=True) and yields an empty recordset.
        integration = self.integration_no_api_1
        model = type(integration)
        found_order = {'id': 'X', 'data': {}, 'updated_at': '2026-06-22T05:00:00Z'}

        with (
            self._patch_adapter(integration, found_order),
            patch.object(model, 'filter_received_orders', return_value=[]),
        ):
            result = integration.fetch_order_by_id('X', raise_error=True)

        self.assertEqual(result, self.env['sale.integration.input.file'])
