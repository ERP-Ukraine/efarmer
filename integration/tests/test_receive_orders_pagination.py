# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

from .config.integration_init import OdooIntegrationInit

_LOGGER_PATH = 'odoo.addons.integration.models.integration_logging'


class TestReceiveOrdersPagination(OdooIntegrationInit):
    """The resume date (last_receive_orders_datetime) must move forward only when the
    whole import run is complete -- never past a page whose max(updated_at) is inflated
    to ~now by the external search-index lag (the order-loss bug)."""

    def _order(self, oid, updated_at):
        return {'id': oid, 'data': {}, 'updated_at': updated_at, 'created_at': updated_at}

    def _run_receive(self, integration, receive_result, page_token=None):
        adapter = MagicMock()
        adapter.receive_orders.return_value = receive_result
        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty), \
                patch.object(model, 'integration_receive_orders_cron') as retrigger:
            integration.integrationApiReceiveOrders(page_token=page_token)
        return retrigger

    def test_resume_date_held_while_more_pages(self):
        # A non-final page must NOT move the resume date, even when it carries an
        # order re-touched to ~now (index-lag poison) that inflates max().
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page = [
            self._order('A', '2026-06-22T05:08:00Z'),
            self._order('POISON', '2026-06-22T05:59:59Z'),
        ]
        retrigger = self._run_receive(integration, (page, 'cursor-1'))

        self.assertEqual(integration.last_receive_orders_datetime, start)
        retrigger.assert_called_once_with(page_token='cursor-1')

    def test_resume_date_moves_forward_on_last_page(self):
        # The final page (no next token) moves the resume date to its own
        # max(updated_at) - 1s and does not re-trigger.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        page = [
            self._order('B', '2026-06-22T05:20:00Z'),
            self._order('C', '2026-06-22T05:25:00Z'),
        ]
        retrigger = self._run_receive(integration, (page, None), page_token='cursor-1')

        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 24, 59),
        )
        retrigger.assert_not_called()

    def test_manual_import_fetches_all_pages_via_token(self):
        # _import_recent_orders follows the token to the end (one synchronous job) and
        # lands the resume date on the LAST page's max, ignoring an earlier page's poison.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        page1 = [self._order('A', '2026-06-22T05:08:00Z'),
                 self._order('POISON', '2026-06-22T05:59:59Z')]
        page2 = [self._order('B', '2026-06-22T05:12:00Z')]
        adapter = MagicMock()
        adapter.receive_orders.side_effect = [(page1, 'cursor-1'), (page2, None)]

        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty):
            integration._import_recent_orders()

        self.assertEqual(adapter.receive_orders.call_count, 2)
        self.assertEqual(adapter.receive_orders.call_args_list[0].kwargs, {'page_token': None})
        self.assertEqual(adapter.receive_orders.call_args_list[1].kwargs, {'page_token': 'cursor-1'})
        # Resume date = last page's max (05:12) - 1s, not page 1's 05:59:59 poison
        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 11, 59),
        )

    def test_manual_import_stops_on_repeated_token(self):
        # Safety net: a connector that keeps handing back the same token must not loop
        # forever -- the synchronous import run stops as soon as a token repeats, and it
        # HOLDS the resume date so the un-fetched orders stay in range for the next run.
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page = [self._order('A', '2026-06-22T05:10:00Z')]
        adapter = MagicMock()
        adapter.receive_orders.return_value = (page, 'stuck-token')  # never changes

        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty), \
                self.assertLogs(_LOGGER_PATH, logging.ERROR) as captured:
            integration._import_recent_orders()
        self.assertTrue(any('stuck-token' in line for line in captured.output))

        # 1st page accepts the token, 2nd page sees it repeat and breaks -> no endless loop
        self.assertEqual(adapter.receive_orders.call_count, 2)
        # Resume date held (not moved to 05:09:59) so nothing is skipped
        self.assertEqual(integration.last_receive_orders_datetime, start)

    def test_async_stops_on_repeated_token(self):
        # Safety net: if a continuation page hands back the same token it was given, the
        # background job must not re-enqueue itself -- it ends the run instead of looping,
        # and HOLDS the resume date so the un-fetched orders stay in range for the next run.
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page = [self._order('A', '2026-06-22T05:20:00Z')]
        with self.assertLogs(_LOGGER_PATH, logging.ERROR) as captured:
            retrigger = self._run_receive(integration, (page, 'stuck-token'), page_token='stuck-token')
        self.assertTrue(any('stuck-token' in line for line in captured.output))

        retrigger.assert_not_called()
        # Resume date held (not moved to 05:19:59) so nothing is skipped
        self.assertEqual(integration.last_receive_orders_datetime, start)
