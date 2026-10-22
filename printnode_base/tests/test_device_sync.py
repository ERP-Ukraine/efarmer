# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPrintNodeCommon


@tagged('post_install', '-at_install', 'pn_account')
class TestPrintNodeDeviceSync(TestPrintNodeCommon):
    """ Exercise device synchronization with real records and mocked API responses.
    """

    def setUp(self):
        super().setUp()
        self.computer.printnode_id = self.computer.id
        self.printers = self.computer.printer_ids
        for printer in self.printers:
            printer.printnode_id = printer.id

        self.printers_uri = f'computers/{self.computer.printnode_id}/printers'
        self.scales_uri = f'computer/{self.computer.printnode_id}/scales'
        self.responses = {
            'computers': [{
                'id': self.computer.printnode_id,
                'name': self.computer.name,
                'state': self.computer.status,
            }],
            self.printers_uri: [{
                'id': printer.printnode_id,
                'name': printer.name,
                'state': printer.status,
            } for printer in self.printers],
            self.scales_uri: [{
                'productId': str(self.scales.printnode_id),
                'deviceName': self.scales.name,
                'deviceNum': self.scales.device_num,
            }],
            'whoami': {'id': 123},
        }
        self.real_request = self.account._send_printnode_request
        self.mock_request = self._create_patch_object(type(self.account), '_send_printnode_request')
        self.mock_request.side_effect = self._device_response
        self.user.write({
            'printnode_printer': self.printer.id,
            'printnode_scales': self.scales.id,
        })
        self.user_rule.printer_bin = self.printer_bin
        self.scenario.printer_id = self.printer
        self.delivery_carrier.printer_id = self.printer
        self.workstation = self.env['printnode.workstation'].create({
            'name': 'Device sync workstation',
            'printer_id': self.printer.id,
            'label_printer_id': self.printer.id,
            'scales_id': self.scales.id,
        })

    def _device_response(self, uri, params=None):
        response = self.responses[uri]
        if params and isinstance(response, list):
            start = 0
            if 'after' in params:
                start = next(i + 1 for i, device in enumerate(response) if device['id'] == params['after'])
            return response[start:start + params['limit']]
        return response

    def _assert_settings_preserved(self):
        self.assertTrue(self.computer.exists())
        self.assertEqual(self.printers.exists(), self.printers)
        self.assertTrue(self.scales.exists())
        self.assertEqual(self.user.printnode_printer, self.printer)
        self.assertEqual(self.user.printnode_scales, self.scales)
        self.assertTrue(self.user_rule.exists())
        self.assertEqual(self.user_rule.printer_id, self.printer)
        self.assertEqual(self.user_rule.printer_bin, self.printer_bin)
        self.assertEqual(self.action_button.printer_id, self.printer)
        self.assertEqual(self.scenario.printer_id, self.printer)
        self.assertEqual(self.delivery_carrier.printer_id, self.printer)
        self.assertEqual(self.workstation.printer_id, self.printer)
        self.assertEqual(self.workstation.label_printer_id, self.printer)
        self.assertEqual(self.workstation.scales_id, self.scales)

    def test_api_key_change_preserves_devices_and_settings(self):
        with patch.object(type(self.account), '_send_dpc_request', return_value={'status_code': 200}), \
                patch.object(type(self.account), 'update_subscription_info_for_account'):
            for active in (True, False):
                with self.subTest(active=active):
                    self.computer.active = active
                    self.printer.active = active
                    self.scales.active = active
                    self.user_rule.active = active
                    self.mock_request.reset_mock()

                    self.account.api_key = f'new-api-key-{active}'

                    self._assert_settings_preserved()
                    self.assertEqual(self.computer.active, active)
                    self.assertEqual(self.printer.active, active)
                    self.assertEqual(self.scales.active, active)
                    self.assertEqual(self.user_rule.active, active)
                    self.assertEqual(self.account.with_context(active_test=False).computer_ids, self.computer)
                    self.assertEqual(self.computer.with_context(active_test=False).printer_ids, self.printers)
                    uris = [args.args[0] for args in self.mock_request.call_args_list]
                    for uri in ('computers', self.printers_uri, self.scales_uri):
                        self.assertEqual(uris.count(uri), 1)

    def test_first_activation_imports_devices_once(self):
        computer_id = 300000
        printers_uri = f'computers/{computer_id}/printers'
        scales_uri = f'computer/{computer_id}/scales'
        self.responses.update({
            'computers': [{'id': computer_id, 'name': 'New Computer', 'state': 'connected'}],
            printers_uri: [{'id': 300001, 'name': 'New Printer', 'state': 'online'}],
            scales_uri: [],
        })

        with patch.object(type(self.account), 'get_main_printnode_account', return_value=False), \
                patch.object(type(self.account), '_send_dpc_request', return_value={'status_code': 200}), \
                patch.object(type(self.account), 'update_subscription_info_for_account'):
            account = self.env['printnode.account'].update_main_account('first-api-key')

        computer = account.computer_ids
        self.assertEqual(computer.printnode_id, computer_id)
        self.assertEqual(computer.printer_ids.printnode_id, 300001)
        uris = [args.args[0] for args in self.mock_request.call_args_list]
        for uri in ('computers', printers_uri, scales_uri):
            self.assertEqual(uris.count(uri), 1)

    def test_first_activation_with_invalid_key_reports_wrong_key(self):
        self.responses.update({'computers': None, 'whoami': None})

        with patch.object(type(self.account), 'get_main_printnode_account', return_value=False), \
                patch.object(type(self.account), '_send_dpc_request', return_value={'status_code': 404}):
            with self.assertRaisesRegex(UserError, 'Wrong API Key'), self.cr.savepoint():
                self.env['printnode.account'].update_main_account('invalid-key')

        self.assertFalse(self.env['printnode.account'].search([('api_key', '=', 'invalid-key')]))
        self.assertNotIn('computers', [args.args[0] for args in self.mock_request.call_args_list])

    def test_invalid_api_key_rolls_back(self):
        old_key = self.account.api_key
        with patch.object(type(self.account), '_send_dpc_request', return_value={'status_code': 400}), \
                patch.object(self.cr, 'commit') as mock_commit:
            with self.assertRaises(UserError), self.cr.savepoint():
                self.account.api_key = 'invalid-key'

            self.assertEqual(self.account.api_key, old_key)
            self._assert_settings_preserved()
            mock_commit.assert_not_called()

    def test_failed_device_requests_preserve_settings(self):
        for method in (self.account.import_devices, self.account.clear_devices_from_odoo):
            for uri in ('computers', self.printers_uri):
                original_response = self.responses[uri]
                for response in (None, False, {}, {'error': 'Unavailable'}, [{}], [None]):
                    with self.subTest(method=method.__name__, uri=uri, response=response):
                        self.responses[uri] = response
                        self.scales.status = 'online'

                        with self.assertRaises(UserError):
                            method()

                        self._assert_settings_preserved()
                        self.assertEqual(self.scales.status, 'online')
                self.responses[uri] = original_response

    def test_scales_api_failure_does_not_block_sync(self):
        self.scales.active = False
        self.responses['computers'][0]['name'] = 'Updated Computer'
        for printer in self.responses[self.printers_uri]:
            printer['state'] = 'online'
        for method in (self.account.import_devices, self.account.clear_devices_from_odoo):
            for response in (None, False, {}, {'error': 'Unavailable'}, [{}], [None]):
                with self.subTest(method=method.__name__, response=response):
                    self.responses[self.scales_uri] = response
                    self.scales.status = 'online'
                    self.computer.name = 'Old Computer'
                    self.printer.status = 'offline'

                    method()

                    self._assert_settings_preserved()
                    self.assertEqual(self.scales.status, 'offline')
                    self.assertFalse(self.scales.active)
                    self.assertEqual(self.computer.name, 'Updated Computer')
                    self.assertEqual(self.printer.status, 'online')

    def test_scales_response_keeps_valid_measurements(self):
        scale = {**self.responses[self.scales_uri][0], 'deviceNum': 7}
        self.responses[self.scales_uri] = [None, {}, scale]

        self.account.clear_devices_from_odoo()

        self._assert_settings_preserved()
        self.assertEqual(self.scales.status, 'online')
        self.assertEqual(self.scales.device_num, 7)

    def test_api_key_change_with_scales_api_failure(self):
        errors = [requests.exceptions.Timeout(), requests.exceptions.ConnectionError()]
        for code, body in ((429, b''), (500, b''), (200, b'not json'), (204, b'')):
            response = requests.Response()
            response.status_code = code
            response._content = body
            errors.append(response)

        def device_response(uri, params=None):
            if uri == self.scales_uri:
                return self.real_request(uri, params=params)
            return self._device_response(uri, params)

        self.mock_request.side_effect = device_response
        for printer in self.responses[self.printers_uri]:
            printer['state'] = 'online'
        with patch.object(type(self.account), '_send_dpc_request', return_value={'status_code': 200}), \
                patch.object(type(self.account), 'update_subscription_info_for_account'), \
                patch.object(type(self.account), '_handle_retry'), \
                patch.object(type(self.account), '_get_requests_method') as mock_method:
            for index, response in enumerate(errors):
                with self.subTest(response=response):
                    if isinstance(response, Exception):
                        mock_method.return_value.side_effect = response
                    else:
                        mock_method.return_value.side_effect = None
                        mock_method.return_value.return_value = response
                    self.scales.status = 'online'

                    self.account.api_key = f'new-key-with-scales-failure-{index}'

                    self.assertEqual(self.account.api_key, f'new-key-with-scales-failure-{index}')
                    self._assert_settings_preserved()
                    self.assertEqual(self.scales.status, 'offline')
                    self.assertEqual(self.printer.status, 'online')

    def test_printer_move_preserves_settings(self):
        printer_id = self.printer.id
        self.printer.active = False
        self.user_rule.active = False
        new_computer_id = 200000
        new_printers_uri = f'computers/{new_computer_id}/printers'
        new_scales_uri = f'computer/{new_computer_id}/scales'
        self.responses['computers'] = [{
            'id': new_computer_id,
            'name': 'New Computer',
            'state': 'connected',
        }]
        self.responses[new_printers_uri] = self.responses.pop(self.printers_uri)
        self.responses[new_scales_uri] = []

        self.account.clear_devices_from_odoo()

        new_computer = self.env['printnode.computer'].search([
            ('printnode_id', '=', new_computer_id),
        ])
        self.assertFalse(self.computer.exists())
        self.assertEqual(self.printer.id, printer_id)
        self.assertTrue(self.printer.exists())
        self.assertEqual(self.printer.computer_id, new_computer)
        self.assertEqual(new_computer.with_context(active_test=False).printer_ids, self.printers)
        self.assertFalse(self.printer.active)
        self.assertTrue(self.printer_bin.exists())
        self.assertEqual(self.user.printnode_printer, self.printer)
        self.assertTrue(self.user_rule.exists())
        self.assertEqual(self.user_rule.printer_id, self.printer)
        self.assertEqual(self.user_rule.printer_bin, self.printer_bin)
        self.assertEqual(self.action_button.printer_id, self.printer)
        self.assertEqual(self.scenario.printer_id, self.printer)
        self.assertEqual(self.delivery_carrier.printer_id, self.printer)
        self.assertEqual(self.workstation.printer_id, self.printer)
        self.assertEqual(self.workstation.label_printer_id, self.printer)

    def test_printer_move_with_existing_computer_preserves_settings(self):
        new_computer_id = 200000
        self.responses['computers'].append({
            'id': new_computer_id,
            'name': 'New Computer',
            'state': 'connected',
        })
        moved_printer = next(
            printer for printer in self.responses[self.printers_uri]
            if printer['id'] == self.printer.printnode_id
        )
        self.responses[self.printers_uri].remove(moved_printer)
        self.responses[f'computers/{new_computer_id}/printers'] = [moved_printer]
        self.responses[f'computer/{new_computer_id}/scales'] = []

        self.account.import_devices()

        self._assert_settings_preserved()
        self.assertEqual(self.printer.computer_id.printnode_id, new_computer_id)
        self.assertNotIn(self.printer, self.computer.printer_ids)

    def test_failed_second_page_preserves_settings(self):
        for uri in ('computers', self.printers_uri):
            with self.subTest(uri=uri):
                first_page = [{
                    'id': 100000 + index,
                    'name': f'Device {index}',
                    'state': 'online',
                } for index in range(100)]

                def response(request_uri, params=None):
                    if request_uri == uri:
                        return None if 'after' in params else first_page
                    return self._device_response(request_uri, params)

                self.mock_request.side_effect = response
                with self.assertRaises(UserError):
                    self.account.clear_devices_from_odoo()
                self._assert_settings_preserved()
                self.assertEqual(self.account.computer_ids, self.computer)
                self.assertEqual(self.computer.printer_ids, self.printers)

    def test_repeated_page_aborts_sync(self):
        page = [{
            'id': 100000 + index,
            'name': f'Computer {index}',
            'state': 'connected',
        } for index in range(100)]
        self.mock_request.side_effect = None
        self.mock_request.return_value = page

        with self.assertRaises(UserError):
            self.account.clear_devices_from_odoo()

        self.assertEqual(self.mock_request.call_count, 2)
        self._assert_settings_preserved()

    def test_printer_on_second_page_keeps_settings(self):
        existing = self.responses[self.printers_uri]
        configured = next(printer for printer in existing if printer['id'] == self.printer.printnode_id)
        self.responses[self.printers_uri] = [{
            'id': 100000 + index,
            'name': f'Printer {index}',
            'state': 'online',
        } for index in range(101 - len(existing))] + [
            printer for printer in existing if printer != configured
        ] + [configured]

        self.account.clear_devices_from_odoo()

        self._assert_settings_preserved()
        self.assertEqual(len(self.computer.printer_ids), 101)
        calls = [args for args in self.mock_request.call_args_list if args.args[0] == self.printers_uri]
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs['params'], {'limit': 100})
        self.assertEqual(calls[1].kwargs['params'], {
            'limit': 100,
            'after': self.responses[self.printers_uri][99]['id'],
        })

    def test_computer_on_second_page_keeps_settings(self):
        extra_computers = [{
            'id': 100000 + index,
            'name': f'Computer {index}',
            'state': 'disconnected',
        } for index in range(100)]
        self.responses['computers'] = extra_computers + self.responses['computers']
        for computer in extra_computers:
            self.responses[f"computers/{computer['id']}/printers"] = []
            self.responses[f"computer/{computer['id']}/scales"] = []

        self.account.clear_devices_from_odoo()

        self._assert_settings_preserved()
        self.assertEqual(len(self.account.computer_ids), 101)
        calls = [args for args in self.mock_request.call_args_list if args.args[0] == 'computers']
        self.assertEqual(len(calls), 2)

    def test_cleanup_removes_missing_archived_printer(self):
        self.printer.active = False
        self.user_rule.active = False
        self.responses[self.printers_uri] = [
            printer for printer in self.responses[self.printers_uri]
            if printer['id'] != self.printer.printnode_id
        ]

        self.account.clear_devices_from_odoo()

        self.assertFalse(self.printer.exists())
        self.assertFalse(self.printer_bin.exists())
        self.assertFalse(self.user_rule.exists())
        self.assertFalse(self.user.printnode_printer)
        self.assertFalse(self.action_button.printer_id)
        self.assertFalse(self.scenario.printer_id)
        self.assertFalse(self.delivery_carrier.printer_id)
        self.assertFalse(self.workstation.printer_id)
        self.assertTrue(self.scales.exists())
        self.assertTrue(self.computer.exists())

    def test_missing_scales_reading_preserves_settings(self):
        self.responses[self.scales_uri] = []
        self.scales.write({'active': False, 'status': 'online'})

        self.account.clear_devices_from_odoo()

        self._assert_settings_preserved()
        self.assertEqual(self.scales.status, 'offline')
        self.assertFalse(self.scales.active)

    def test_cleanup_empty_account_preserves_other_account(self):
        self.responses['computers'] = []
        other_account = self.env['printnode.account'].create({'api_key': 'other-api-key'})
        other_computer = self.computer.copy({'account_id': other_account.id, 'printnode_id': 200000})
        other_printer = self.printer.copy({'computer_id': other_computer.id, 'printnode_id': 200000})
        other_scales = self.scales.copy({'computer_id': other_computer.id, 'status': 'online'})
        self.computer.active = False
        self.printer.active = False
        self.scales.active = False
        self.user_rule.active = False

        self.account.clear_devices_from_odoo()

        self.assertFalse(self.computer.exists())
        self.assertFalse(self.printers.exists())
        self.assertFalse(self.scales.exists())
        self.assertFalse(self.user_rule.exists())
        self.assertFalse(self.user.printnode_printer)
        self.assertFalse(self.user.printnode_scales)
        self.assertFalse(self.workstation.scales_id)
        self.assertTrue(other_computer.exists())
        self.assertTrue(other_printer.exists())
        self.assertTrue(other_scales.exists())
        self.assertEqual(other_scales.status, 'online')

    def test_http_failures_do_not_delete_devices(self):
        errors = [requests.exceptions.Timeout(), requests.exceptions.ConnectionError()]
        for code, body in ((429, b''), (500, b''), (200, b'not json'), (204, b'')):
            response = requests.Response()
            response.status_code = code
            response._content = body
            errors.append(response)

        with patch.object(type(self.account), '_handle_retry'), \
                patch.object(type(self.account), '_get_requests_method') as mock_method:
            for response in errors:
                with self.subTest(response=response):
                    if isinstance(response, Exception):
                        mock_method.return_value.side_effect = response
                    else:
                        mock_method.return_value.side_effect = None
                        mock_method.return_value.return_value = response
                    self.mock_request.side_effect = self.real_request

                    with self.assertRaises(UserError):
                        self.account.clear_devices_from_odoo()

                    self._assert_settings_preserved()
