# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.addons.integration.models import sale_integration as si

from .config.integration_init import OdooIntegrationInit

_LOGGER_PATH = 'odoo.addons.integration.models.integration_logging'


class TestReceiveOrdersPagination(OdooIntegrationInit):
    """The resume date (last_receive_orders_datetime) moves forward only when the whole
    import run is complete, and to max(updated_at) across ALL pages of the run. Pages are
    ordered by the connector's immutable id, so the newest order may sit on any page (or
    before an empty final page); the driver carries that max through the run."""

    def _order(self, oid, updated_at):
        return {'id': oid, 'data': {}, 'updated_at': updated_at, 'created_at': updated_at}

    def _run_receive(self, integration, receive_result, page_token=None, max_updated_at=None, page_no=1):
        adapter = MagicMock()
        adapter.receive_orders.return_value = receive_result
        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty), \
                patch.object(model, 'integration_receive_orders_cron') as retrigger:
            integration.integrationApiReceiveOrders(
                page_token=page_token, max_updated_at=max_updated_at, page_no=page_no)
        return retrigger

    def test_resume_date_held_while_more_pages(self):
        # A non-final page must NOT move the resume date; it enqueues the next page and
        # threads the running max(updated_at) + update_dt to it.
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page = [
            self._order('A', '2026-06-22T05:08:00Z'),
            self._order('B', '2026-06-22T05:40:00Z'),
        ]
        retrigger = self._run_receive(integration, (page, 'cursor-1'))

        self.assertEqual(integration.last_receive_orders_datetime, start)
        retrigger.assert_called_once_with(
            page_token='cursor-1', max_updated_at='2026-06-22T05:40:00Z', update_dt=True, page_no=2)

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

    def test_async_resume_uses_max_across_pages_not_last_page(self):
        # Pages are id-ordered, so the final page's updated_at (05:12) can be OLDER than an
        # earlier page's (carried as 05:59). The resume date must use the carried max, not
        # the last page -- otherwise it would regress and re-scan the backlog every run.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        page = [self._order('B', '2026-06-22T05:12:00Z')]
        self._run_receive(
            integration, (page, None), page_token='cursor-2', max_updated_at='2026-06-22T05:59:00Z')

        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 58, 59),
        )

    def test_async_empty_last_page_still_moves_resume_date(self):
        # Backlog was an exact multiple of the page size, so the final page is empty. The
        # max carried from earlier pages still moves the resume date forward (no wasted
        # full re-scan next run).
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        self._run_receive(
            integration, ([], None), page_token='cursor-2', max_updated_at='2026-06-22T05:30:00Z')

        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 29, 59),
        )

    def test_manual_import_fetches_all_pages_via_token(self):
        # _import_recent_orders follows the token to the end (one synchronous job) and lands
        # the resume date on max(updated_at) across ALL pages, not just the last one.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        # id-ordered pages: page 1 carries the newest order (05:59), the last page an older one.
        page1 = [self._order('A', '2026-06-22T05:08:00Z'),
                 self._order('NEWEST', '2026-06-22T05:59:59Z')]
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
        # Resume date = max across all pages (05:59:59) - 1s, not the last page's 05:12
        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 59, 58),
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

    def test_async_page_cap_bounds_the_job_chain(self):
        # A connector that never signals the last page must not grow the job chain forever:
        # once the page counter reaches the cap, the chain stops (no re-enqueue) and holds
        # the resume date.
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page = [self._order('A', '2026-06-22T05:20:00Z')]
        with self.assertLogs(_LOGGER_PATH, logging.ERROR) as captured:
            retrigger = self._run_receive(
                integration, (page, 'more-token'), page_token='prev-token',
                page_no=si.RECEIVE_ORDERS_MAX_PAGES, max_updated_at='2026-06-22T05:20:00Z')
        self.assertTrue(any('page cap' in line for line in captured.output))

        retrigger.assert_not_called()  # chain stopped instead of enqueuing another page
        self.assertEqual(integration.last_receive_orders_datetime, start)  # date held

    def test_manual_import_hands_off_after_page_cap(self):
        # Manual import runs in one transaction, so it stops at the manual cap and hands the
        # remaining pages to the background chain (carrying the running max), holding the
        # resume date -- the chain moves it forward on its own final page.
        integration = self.integration_no_api_1
        start = datetime(2026, 6, 22, 5, 0, 0)
        integration.last_receive_orders_datetime = start

        page1 = [self._order('A', '2026-06-22T05:10:00Z')]
        page2 = [self._order('B', '2026-06-22T05:20:00Z')]
        adapter = MagicMock()
        adapter.receive_orders.side_effect = [(page1, 'cursor-1'), (page2, 'cursor-2')]

        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with self.assertLogs(_LOGGER_PATH, logging.WARNING) as captured, \
                patch.object(si, 'MANUAL_IMPORT_MAX_PAGES', 2), \
                patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty), \
                patch.object(model, 'integration_receive_orders_cron') as handoff:
            integration._import_recent_orders()
        self.assertTrue(any('manual page cap' in line for line in captured.output))

        # Fetched exactly the capped number of pages, then handed the rest off from cursor-2
        self.assertEqual(adapter.receive_orders.call_count, 2)
        handoff.assert_called_once_with(
            page_token='cursor-2', max_updated_at='2026-06-22T05:20:00Z', update_dt=True)
        # Resume date HELD (partial run) so the un-fetched orders stay in range
        self.assertEqual(integration.last_receive_orders_datetime, start)

    def test_async_full_chain_advances_resume_to_global_max(self):
        # End-to-end: run the WHOLE async job chain (not a single mocked page). Each enqueue
        # runs the next page in-process, threading page_token/max_updated_at/page_no. With
        # id-ordered pages the newest updated_at (05:59) sits on page 1 and the oldest on the
        # last page; the run must still finish with the resume date at the global max.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        pages = [
            ([self._order('A', '2026-06-22T05:59:00Z')], 'cursor-1'),
            ([self._order('B', '2026-06-22T05:30:00Z')], 'cursor-2'),
            ([self._order('C', '2026-06-22T05:10:00Z')], None),
        ]
        adapter = MagicMock()
        adapter.receive_orders.side_effect = pages
        model = type(integration)
        empty = self.env['sale.integration.input.file']

        def _run_next_page(rec, page_token=None, update_dt=True, max_updated_at=None, page_no=1):
            # Stand-in for the queue job: execute the next page synchronously, in-process.
            return rec.integrationApiReceiveOrders(
                page_token=page_token, update_dt=update_dt,
                max_updated_at=max_updated_at, page_no=page_no)

        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data', return_value=empty), \
                patch.object(model, 'integration_receive_orders_cron', _run_next_page):
            integration.integrationApiReceiveOrders()  # kicks off page 1 -> chains to the end

        self.assertEqual(adapter.receive_orders.call_count, 3)
        # Resume = max across ALL pages (05:59) - 1s, never the last page's 05:10
        self.assertEqual(
            integration.last_receive_orders_datetime,
            datetime(2026, 6, 22, 5, 58, 59),
        )

    def test_input_file_creation_is_idempotent(self):
        # The whole no-loss argument rests on this: re-fetching an already-imported order
        # (which HELD resume dates cause on the next run) must NOT create a duplicate -- it
        # returns the existing input file, keyed by external id.
        # skip_create_order_from_input keeps the test to the dedup logic (no processing pipeline)
        integration = self.integration_no_api_1.with_context(skip_create_order_from_input=True)
        data = {
            'id': 'EXT-1',
            'data': {'foo': 'bar'},
            'updated_at': '2026-06-22T05:00:00Z',
            'created_at': '2026-06-22T05:00:00Z',
        }
        first = integration._create_input_file_from_received_data(data)
        second = integration._create_input_file_from_received_data(data)

        self.assertEqual(first, second)
        self.assertEqual(
            self.env['sale.integration.input.file'].search_count(
                [('si_id', '=', integration.id), ('name', '=', 'EXT-1')]),
            1,
        )

    def test_keyset_survives_order_leaving_set_mid_run(self):
        # Regression for the removal/skip bug. A STATEFUL fake store (unlike our static-page
        # mocks) recomputes each page against its live contents. Order #2, already read on
        # page 1, leaves the set between pages (status change / deletion). With a keyset by id
        # (token = last id, next page = id > token) the un-read orders cannot shift, so nothing
        # is skipped. Offset pagination would drop order #3 here.
        integration = self.integration_no_api_1
        integration.last_receive_orders_datetime = datetime(2026, 6, 22, 5, 0, 0)

        PAGE = 2
        state = {
            'orders': [(i, '2026-06-22T05:0%s:00Z' % i) for i in range(1, 6)],  # ids 1..5
            'calls': 0,
        }

        def keyset_receive(page_token=None):
            state['calls'] += 1
            last_id = page_token or 0
            rows = [o for o in state['orders'] if o[0] > last_id][:PAGE]  # id > token
            if state['calls'] == 1:  # order #2 leaves the set right after page 1
                state['orders'] = [o for o in state['orders'] if o[0] != 2]
            result = [self._order(str(oid), upd) for oid, upd in rows]
            next_token = rows[-1][0] if len(rows) == PAGE else None
            return result, next_token

        adapter = MagicMock()
        adapter.receive_orders.side_effect = lambda page_token=None: keyset_receive(page_token)

        imported = []
        model = type(integration)
        empty = self.env['sale.integration.input.file']
        with patch.object(model, '_build_adapter', return_value=adapter), \
                patch.object(model, '_create_input_file_from_received_data',
                             side_effect=lambda data: imported.append(data['id']) or empty):
            integration._import_recent_orders()

        # Every order is imported; order #3 (the offset-victim) is NOT skipped.
        self.assertEqual(sorted(imported), ['1', '2', '3', '4', '5'])
