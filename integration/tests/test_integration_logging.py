# See LICENSE file for full copyright and licensing details.

import logging

from .config.integration_init import OdooIntegrationInit

# NOTE on assertLogs level: Odoo remaps the level *name* "INFO" to 25 via
# ``logging.addLevelName(RUNBOT, "INFO")`` in odoo/netsvc.py, so passing the string
# ``'INFO'`` makes assertLogs gate at 25 and silently miss ``logger.info()`` records
# (emitted at the constant level 20). Always pass the integer ``logging.INFO`` instead.

_LOGGER_PATH = 'odoo.addons.integration.models.integration_logging'


class TestIntegrationLoggingWriteLog(OdooIntegrationInit):
    """write_log() always emits to the server log, and additionally persists a row in the
    integration.logging model only when 'Save Logs' is on AND the event type is selected.
    Every caller (webhooks, customer sync, order import, ...) relies on this single gate, so
    it is tested here once rather than through each caller."""

    def setUp(self):
        super().setUp()
        self.integration = self.integration_no_api_1
        self.log_model = self.env['integration.logging']
        self.order_import_type = self.env.ref('integration.integration_log_type_order_import')

    def _count(self, event_type='order_import'):
        return self.log_model.search_count([
            ('integration_id', '=', self.integration.id),
            ('event_type', '=', event_type),
        ])

    def _latest(self, event_type='order_import'):
        return self.log_model.search([
            ('integration_id', '=', self.integration.id),
            ('event_type', '=', event_type),
        ], limit=1, order='id desc')

    def test_persists_when_enabled_and_type_selected(self):
        self.integration.save_log = True
        self.integration.log_type_ids = [(6, 0, self.order_import_type.ids)]

        before = self._count()
        self.log_model.write_log(
            self.integration, 'order_import', 'Event', 'A message', log_level='info')

        self.assertEqual(self._count(), before + 1)
        row = self._latest()
        self.assertEqual(row.event_name, 'Event')
        self.assertEqual(row.message, 'A message')

    def test_no_persist_when_save_log_off(self):
        self.integration.save_log = False
        self.integration.log_type_ids = [(6, 0, self.order_import_type.ids)]

        before = self._count()
        self.log_model.write_log(self.integration, 'order_import', 'Event', 'msg', log_level='info')
        self.assertEqual(self._count(), before)

    def test_no_persist_when_type_not_selected(self):
        self.integration.save_log = True
        self.integration.log_type_ids = [(6, 0, [])]  # save on, but order_import not selected

        before = self._count()
        self.log_model.write_log(self.integration, 'order_import', 'Event', 'msg', log_level='info')
        self.assertEqual(self._count(), before)

    def test_always_writes_server_log_even_when_persistence_off(self):
        self.integration.save_log = False
        with self.assertLogs(_LOGGER_PATH, logging.INFO) as captured:
            self.log_model.write_log(
                self.integration, 'order_import', 'Event', 'hello world', log_level='info')
        text = '\n'.join(captured.output)
        self.assertIn(self.integration.name, text)
        self.assertIn('hello world', text)

    def test_log_level_is_respected(self):
        self.integration.save_log = False
        # An 'error' call is captured when watching at ERROR...
        with self.assertLogs(_LOGGER_PATH, logging.ERROR) as captured:
            self.log_model.write_log(
                self.integration, 'order_import', 'Boom', 'failure detail', log_level='error')
        self.assertTrue(any('failure detail' in line for line in captured.output))

        # ...while an 'info' call is not (proving the level argument is honoured).
        with self.assertRaises(AssertionError):
            with self.assertLogs(_LOGGER_PATH, logging.ERROR):
                self.log_model.write_log(
                    self.integration, 'order_import', 'Quiet', 'info detail', log_level='info')

    def test_res_model_and_res_id_are_stored(self):
        self.integration.save_log = True
        self.integration.log_type_ids = [(6, 0, self.order_import_type.ids)]

        self.log_model.write_log(
            self.integration, 'order_import', 'Linked', 'msg',
            res_model='sale.integration', res_id=self.integration.id, log_level='info')

        row = self._latest()
        self.assertEqual(row.res_model, 'sale.integration')
        self.assertEqual(row.res_id, self.integration.id)

    def test_noop_without_integration(self):
        # Guard clause: a falsy integration must be a no-op, not a crash.
        self.assertIsNone(self.log_model.write_log(False, 'order_import', 'Event', 'msg'))
