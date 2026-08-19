# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from datetime import date

import requests
from unittest.mock import patch, call

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TestPrintNodeCommon, TEST_COMPUTERS_FROM_PRINTNODE, \
    TEST_PRINTERS_FROM_PRINTNODE, TEST_SCALES_FROM_PRINTNODE

# Copied from request library to provide compatibility with the library
try:
    from simplejson import JSONDecodeError
except ImportError:
    from json import JSONDecodeError


SUBSCRIPTION_INFO_RESPONSE = {
    'data': {
        'stats': {
            'printed': 3,
            'limits': 5,
        },
        'subscription_details': {
            'subscription_status': 'active',
            'subscription_plan': 'Business',
            'subscription_start_date': '2026-01-01',
            'subscription_end_date': '2026-12-31',
        },
    },
    'status_code': 200,
}
MAX_RETRIES = 3
PRINTNODE_STATISTICS = {"current": {"prints": 10, }, }
PRINTNODE_BILLING_PLAN = {"current": {"printCurve": '("{0,5000}","{0,0}",0.0018)', }, }


@tagged('post_install', '-at_install', 'pn_account')  # can be run by test-tag
class TestPrintNodeAccount(TestPrintNodeCommon):
    """
    Tests of Account model methods
    """

    def setUp(self):
        super(TestPrintNodeAccount, self).setUp()

        self.computer_2 = self.env['printnode.computer'].create({
            'name': 'VENTORTECH-DEV',
            # 'printnode_id': 413,
            'status': 'disconnected',
            'account_id': self.account.id,
        })

        self.printer_2 = self.env['printnode.printer'].create({
            'name': 'PDF',
            # 'printnode_id': 710,
            'status': 'online',
            'computer_id': self.computer_2.id,
        })

        self.printer_bin_2 = self.env['printnode.printer.bin'].create({
            'name': 'Test Bin #2',
            'printer_id': self.printer_2.id,
        })

        self.printer_job = self.env['printnode.printjob'].create({
            'printer_id': self.printer.id,
            'description': 'Test print',
        })

        self.printer_job_2 = self.env['printnode.printjob'].create({
            'printer_id': self.printer_2.id,
            'description': 'Test print #2',
        })

        self.scales_2 = self.env['printnode.scales'].create({
            'name': 'Local Test Scales 2',
            'device_num': 3,
            # 'printnode_id': 730,
            'status': 'offline',
            'computer_id': self.computer_2.id,
        })

        self.action_button.update({
            'printer_id': self.printer.id,
        })

        self.user_rule.update({
            'printer_id': self.printer.id,
        })

        self.scenario.update({
            'printer_id': self.printer.id,
        })

        self.delivery_carrier.update({
            'printer_id': self.printer.id,
        })

    def test_deactivate_printers(self):
        """
        Test for correct deactivation of printers
        """

        self.printer.status = 'online'
        self.assertEqual(self.printer.status, 'online')

        self.account._deactivate_printers()
        self.assertEqual(self.printer.status, 'offline', "Deactivation of printers failed")

    def test_deactivate_devices(self):
        """
        Test for correct deactivation of scales
        """

        self.scales.status = 'online'
        self.assertEqual(self.scales.status, 'online')

        self.account._deactivate_devices()
        self.assertEqual(self.scales.status, 'offline', "Deactivation of scales failed")

    def test_send_printnode_request(self):
        """
        This is a case for testing the logic of the send_printnode_request method from
        the printnode_account model.
        This does not test api('https://api.printnode.com/') for stability!
        Should be provided other tools for API testing. If the api fails - this test case won't
        determine it.
        """

        get_result = requests.Response()
        get_result.__dict__.update({
            '_content': b'{"creatorEmail":"test_printnode_dev@ventor.tech"}\n',
            '_content_consumed': True,
            'status_code': 200,
            'apparent_encoding': 'ascii',
            'ok': True,
        })

        with self.cr.savepoint(), patch.object(requests, 'get', return_value=get_result):
            json_response = self.account._send_printnode_request('something')
            self.assertEqual(self.account.status, 'OK')
            self.assertTrue(json_response)

        get_result.__dict__.update({
            '_content': False,
            '_content_consumed': False,
            'status_code': 404,
            'apparent_encoding': None,
            'ok': False,
        })

        self.printer.status = 'online'
        with self.cr.savepoint(), patch.object(requests, 'get', return_value=get_result) as mock_requests_get:
            mock_requests_get.side_effect = requests.exceptions.ConnectionError('ConnectionError')

            json_response = self.account._send_printnode_request('something')
            self.assertEqual(self.account.status, 'ConnectionError')
            self.assertIsNone(json_response)
            self.assertEqual(self.printer.status, 'offline')
            self.assertEqual(mock_requests_get.call_count, MAX_RETRIES + 1)

        self.printer.status = 'online'
        with self.cr.savepoint(), patch.object(requests, 'get', return_value=get_result) as mock_requests_get:
            mock_requests_get.side_effect = requests.exceptions.RequestException('RequestException')

            json_response = self.account._send_printnode_request('something')
            self.assertEqual(self.account.status, 'RequestException')
            self.assertIsNone(json_response)
            self.assertEqual(self.printer.status, 'offline')
            self.assertEqual(mock_requests_get.call_count, MAX_RETRIES + 1)

    def test_create_or_update_scales(self):
        """
        Test for correct creating or updating scales
        """

        test_scales_1 = {
            'productId': '1',
            'deviceName': 'Local Test Scales 1',
        }
        self.assertNotEqual(self.scales.name, 'Local Test Scales 1')

        # Update scales
        self.account._create_or_update_scales(test_scales_1, self.computer)

        self.assertEqual(
            self.env['printnode.scales'].search([
                ('printnode_id', '=', int(test_scales_1['productId']))
            ]),
            self.scales
        )
        self.assertEqual(self.scales.name, 'Local Test Scales 1')

        # Create new scales
        test_scales_2 = TEST_SCALES_FROM_PRINTNODE[0]
        self.account._create_or_update_scales(test_scales_2, self.computer)

        self.assertEqual(self.env['printnode.scales'].search_count([]), 3)
        self.assertEqual(
            self.env['printnode.scales'].search([
                ('device_num', '=', int(test_scales_2['deviceNum'])),
            ]).name,
            'Local Test Scales 2'
        )

    def test_unlink_devices(self):
        """
        Test for correct deleting computers, printers, print jobs and user rules
        """

        self.assertTrue(self.env['printnode.rule'].search_count([]) > 0)
        self.assertTrue(self.env['printnode.printjob'].search_count([]) > 0)
        self.assertTrue(self.env['printnode.printer'].search_count([]) > 0)
        self.assertTrue(self.env['printnode.computer'].search_count([]) > 0)

        self.account.unlink_devices()

        self.assertEqual(self.env['printnode.rule'].search_count([]), 0)
        self.assertEqual(self.env['printnode.printjob'].search_count([]), 0)
        self.assertEqual(self.env['printnode.printer'].search_count([]), 0)
        self.assertEqual(self.env['printnode.computer'].search_count([]), 0)

    def test_get_node(self):
        """
        Test for correct parsing and updating Direct Print nodes (printer and computers)
        """

        # Computers
        test_computers = TEST_COMPUTERS_FROM_PRINTNODE

        test_odoo_computer = self.account._get_node('computer', test_computers[0], self.account.id)
        self.assertTrue(test_odoo_computer)
        self.assertEqual(test_odoo_computer['name'], 'VENTORTECH-DEV')

        test_computers[0].update({'name': 'TEST-NAME'})
        count_odoo_computers = self.env['printnode.computer'].search_count([])
        test_odoo_computer = self.account._get_node('computer', test_computers[0], self.account.id)
        self.assertEqual(count_odoo_computers, self.env['printnode.computer'].search_count([]))
        self.assertEqual(test_odoo_computer['name'], 'TEST-NAME')

        # Printers
        test_printers = TEST_PRINTERS_FROM_PRINTNODE

        test_odoo_printer = self.account._get_node(
            'printer',
            test_printers[0],
            test_odoo_computer.id,
        )
        self.assertTrue(test_odoo_printer)
        self.assertEqual(test_odoo_printer['name'], 'PDF')

        test_printers[0].update({'name': 'TEST-NAME'})
        count_odoo_printers = self.env['printnode.printer'].search_count([])
        test_odoo_printer = self.account._get_node(
            'printer',
            test_printers[0],
            test_odoo_computer.id,
        )
        self.assertEqual(count_odoo_printers, self.env['printnode.printer'].search_count([]))
        self.assertEqual(test_odoo_printer['name'], 'TEST-NAME')

    def test_get_limits(self):
        """
        Test for correct getting limits of print from 'printnode.account' with status is 'OK'
        """

        self.account.update({
            'printed': 1,
            'limits': 2,
            'status': '401'
        })
        self.assertEqual(
            self.account.get_limits(),
            [{'account': 'Default Account', 'error': '401'}],
        )

        self.account.status = 'OK'
        self.assertEqual(
            self.account.get_limits(),
            [{'account': 'Default Account', 'printed': 1, 'limits': 2}],
        )

    def test_recheck_printer(self):
        """
        Test for correct re-checking particular printer status.
        This does not test api('https://api.printnode.com/') for stability!
        Should be provided other tools for API testing. If the api fails - this test case won't
        determine it.
        """
        self.env.company.printnode_recheck = True
        test_printers = TEST_PRINTERS_FROM_PRINTNODE

        # Printer status - "online"
        # Computer status - "disconnected"
        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request', ) \
                as mock_account:
            mock_account.return_value = test_printers
            test_rechecked_printer = self.account.recheck_printer(self.printer)
            self.assertFalse(self.printer.online)
            self.assertFalse(test_rechecked_printer)

        # Printer status - "online"
        # Computer status - "connected"
        test_printers[0]['computer']['state'] = 'connected'
        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request', ) \
                as mock_account:
            mock_account.return_value = test_printers
            test_rechecked_printer = self.account.recheck_printer(self.printer)
            self.assertTrue(self.printer.online)
            self.assertTrue(test_rechecked_printer)

        # Printer status - "offline"
        test_printers[0]['state'] = 'offline'
        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request', ) \
                as mock_account:
            mock_account.return_value = test_printers
            test_rechecked_printer = self.account.recheck_printer(self.printer)
            self.assertFalse(self.printer.online)
            self.assertFalse(test_rechecked_printer)

    def test_import_devices(self):
        """
        Test for correct re-importing list of devices into OpenERP.
        This does not test api('https://api.printnode.com/') for stability!
        Should be provided other tools for API testing. If the api fails - this test case won't
        determine it.
        """

        test_computers = TEST_COMPUTERS_FROM_PRINTNODE
        test_printers = TEST_PRINTERS_FROM_PRINTNODE
        test_scales = TEST_SCALES_FROM_PRINTNODE

        self.assertEqual(self.env['printnode.computer'].search_count([]), 2)
        self.assertEqual(self.env['printnode.printer'].search_count([]), 5)
        self.assertEqual(self.env['printnode.scales'].search_count([]), 2)

        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request') as \
                mock_account_send_printnode_request:
            def side_effect_send_printnode_request(uri: str, params=None):
                if uri == 'computers':
                    return test_computers

                if 'computers' in uri and 'printers' in uri:
                    return test_printers

                if 'computer' in uri and 'scales' in uri:
                    return test_scales

                return None

            mock_account_send_printnode_request.return_value = None
            mock_account_send_printnode_request.side_effect = side_effect_send_printnode_request

            self.account.import_devices()
            self.assertEqual(mock_account_send_printnode_request.call_count, 3)

            self.assertEqual(self.env['printnode.computer'].search_count([]), 3)
            self.assertEqual(self.env['printnode.printer'].search_count([]), 6)
            self.assertEqual(self.env['printnode.scales'].search_count([]), 3)

    def test_clear_devices_from_odoo(self):
        """
        Test to check deleting of devices from Odoo which
        not presented in the Direct Print Account
        """

        # Set Up
        self.computer_2.update({
            'printnode_id': 413,
        })
        self.printer_2.update({
            'printnode_id': 710,
        })
        self.scales_2.update({
            'printnode_id': 730,
        })

        # The number of the following entities will decrease
        self.assertEqual(self.env['printnode.computer'].search_count([]), 2)
        self.assertEqual(self.env['printnode.printer'].search_count([]), 5)
        self.assertEqual(self.env['printnode.printer.bin'].search_count([]), 2)
        self.assertEqual(self.env['printnode.printjob'].search_count([]), 2)
        self.assertEqual(self.env['printnode.scales'].search_count([]), 2)
        self.assertEqual(self.env['printnode.rule'].search_count([]), 1)

        # The state of the "printer_id" field of the following entities will change
        self.assertEqual(self.action_button.printer_id, self.printer)
        self.assertEqual(self.scenario.printer_id, self.printer)
        self.assertEqual(self.delivery_carrier.printer_id, self.printer)

        mock_import_devices = \
            self._create_patch_object(type(self.account), 'import_devices')
        mock_import_devices.return_value = None

        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request') as \
                mock_send_printnode_request:
            def side_effect_send_printnode_request(uri: str, params=None):
                if uri == 'computers':
                    return TEST_COMPUTERS_FROM_PRINTNODE

                return TEST_PRINTERS_FROM_PRINTNODE

            mock_send_printnode_request.side_effect = side_effect_send_printnode_request

            # Clear devices
            self.account.clear_devices_from_odoo()

            self.assertEqual(self.env['printnode.computer'].search_count([]), 1)
            self.assertEqual(self.env['printnode.printer'].search_count([]), 1)
            self.assertEqual(self.env['printnode.printer.bin'].search_count([]), 1)
            self.assertEqual(self.env['printnode.printjob'].search_count([]), 1)
            self.assertEqual(self.env['printnode.scales'].search_count([]), 1)
            self.assertEqual(self.env['printnode.rule'].search_count([]), 0)

            self.assertFalse(self.action_button.printer_id)
            self.assertFalse(self.delivery_carrier.printer_id)
            self.assertFalse(self.scenario.printer_id)
            mock_import_devices.assert_called_once()

    def test_account_write(self):
        """
        Account activation test if API key has been changed.
        If the API key has been changed, then in addition to the 'write'
        method, the 'activate_account' method will also be called.
        """

        account_id = self.account.id
        account_api_key = self.account.api_key

        with self.cr.savepoint(), patch.object(type(self.account), 'activate_account') \
                as mock_activate_account:
            self.account.api_key = 'test_apikey'
            mock_activate_account.assert_called_once()
            self.assertEqual(self.account.id, account_id)
            self.assertNotEqual(self.account.api_key, account_api_key)

    def test_update_main_account(self):
        """
        Test updating main account
        """

        self.assertEqual(self.env['printnode.account'].search([]), self.account)

        # Without run 'activate_account' method
        # Check update_main_account() with correct key
        with self.cr.savepoint(), patch.object(type(self.account), 'activate_account') \
                as mock_activate_account:
            self.account.update_main_account('test_apikey')
            mock_activate_account.assert_called_once()
            self.assertEqual(self.env['printnode.account'].search([]), self.account)
            self.assertEqual(self.env['printnode.account'].search([]).api_key, 'test_apikey')

        # Check update_main_account() with empty key
        self.account.update_main_account(None)
        self.assertEqual(self.env['printnode.account'].search_count([]), 0)

        # Check update_main_account() with another correct key
        with self.cr.savepoint(), patch.object(type(self.account), 'activate_account') \
                as mock_activate_account:
            self.account.update_main_account('test_apikey_2')
            mock_activate_account.assert_called_once()
            self.assertEqual(self.env['printnode.account'].search([]).api_key, 'test_apikey_2')

    def test_send_dpc_request(self):
        """
        This is a case for testing the logic of the _send_dpc_request method from
        the printnode_account model.
        This does not test api 'https://print.api<.dev>.ventor.tech' for stability!
        Should be provided other tools for API testing. If the api fails - this test case won't
        determine it.
        """

        # Check _send_dpc_request() with wrong params
        # Expected ValueError
        with self.assertRaises(ValueError):
            self.account._send_dpc_request('DEL', 'something')

        resp = requests.Response()
        resp.__dict__.update({
            'data': {
                'id': 1,
            },
            'status_code': 200,
            '_content': b'{"email":"test_ventor_tech@print.ventor.tech"}\n',
            '_content_consumed': True,
        })

        # Check _send_dpc_request() with patched 'get' method from "requests"
        # Expected account status - Ok
        with self.cr.savepoint(), patch.object(requests, 'get', return_value=resp, ) \
                as mock_requests_get:
            json_response = self.account._send_dpc_request('GET', 'something')
            self.assertTrue(json_response)
            self.assertEqual(self.account.status, 'OK')
            mock_requests_get.assert_called_once()

        # Added side_effect - ConnectionError
        # Expected account status - 'ConnectionError'
        self.printer.status = 'online'
        with self.cr.savepoint(), patch.object(requests, 'get', ) as mock_requests_get:
            mock_requests_get.side_effect = requests.exceptions.ConnectionError('ConnectionError')
            json_response = self.account._send_dpc_request('GET', 'something')
            self.assertEqual(self.account.status, 'ConnectionError')
            self.assertIsNone(json_response)
            self.assertEqual(self.printer.status, 'offline')
            mock_requests_get.assert_called_once()

        # Added side_effect - RequestException
        # Expected account status - 'RequestException'
        self.printer.status = 'online'
        with self.cr.savepoint(), patch.object(requests, 'get', ) as mock_requests_get:
            mock_requests_get.side_effect = requests.exceptions.RequestException('RequestException')
            json_response = self.account._send_dpc_request('GET', 'something')
            self.assertEqual(self.account.status, 'RequestException')
            self.assertIsNone(json_response)
            self.assertEqual(self.printer.status, 'offline')
            mock_requests_get.assert_called_once()

        # Added side_effect - JSONDecodeError
        # Expected account status - 'JSONDecodeError'
        self.printer.status = 'online'
        with self.cr.savepoint(), patch.object(requests, 'get', ) as mock_requests_get:
            mock_requests_get.side_effect = JSONDecodeError('JSONDecodeError', 'err', 1)
            json_response = self.account._send_dpc_request('GET', 'something')
            self.assertEqual(self.account.status, 'JSONDecodeError: line 1 column 2 (char 1)')
            self.assertIsNone(json_response)
            self.assertEqual(self.printer.status, 'offline')
            mock_requests_get.assert_called_once()

    def test_get_limits_printnode(self):
        """
        Test getting limits (printed pages + total available pages) from Direct Print
        """

        with self.cr.savepoint(), patch.object(type(self.account), '_send_printnode_request', ) \
                as mock_send_printnode_request:
            def side_effect_send_printnode_request(uri: str, params=None):
                vals = {
                    'billing/statistics': PRINTNODE_STATISTICS,
                    'billing/plan': PRINTNODE_BILLING_PLAN
                }
                return vals[uri]

            mock_send_printnode_request.side_effect = side_effect_send_printnode_request
            printed, limits = self.account._get_limits_printnode()
            self.assertEqual(printed, 10)
            self.assertEqual(limits, '5000')
            self.assertEqual(mock_send_printnode_request.call_count, 2)
            self.assertEqual(
                mock_send_printnode_request.call_args_list,
                [call('billing/statistics'), call('billing/plan')]
            )

    @mute_logger('odoo.addons.printnode_base.models.printnode_account')
    def test_update_subscription_info_for_account(self):
        """
        Tests updating limits and subscription information for current account
        """

        self.account.update({
            'is_dpc_account': True,
            'printed': 0,
            'limits': 0,
        })

        with self.cr.savepoint(), patch.object(type(self.account), '_send_dpc_request', ) \
                as mock_send_dpc_request:
            mock_send_dpc_request.return_value = SUBSCRIPTION_INFO_RESPONSE

            subscription_status = self.account.update_subscription_info_for_account()

            self.assertEqual(subscription_status, 'active')
            self.assertEqual(self.account.printed, 3)
            self.assertEqual(self.account.limits, 5)
            self.assertEqual(self.account.subscription_status, 'active')
            self.assertEqual(self.account.subscription_plan, 'Business')
            self.assertEqual(self.account.subscription_start_date, date(2026, 1, 1))
            self.assertEqual(self.account.subscription_end_date, date(2026, 12, 31))
            mock_send_dpc_request.assert_called_once_with(
                'GET',
                'api-keys',
                headers={'DPC-API-Key': self.account.api_key},
            )

        response_with_unknown_status = {
            **SUBSCRIPTION_INFO_RESPONSE,
            'data': {
                **SUBSCRIPTION_INFO_RESPONSE['data'],
                'subscription_details': {
                    **SUBSCRIPTION_INFO_RESPONSE['data']['subscription_details'],
                    'subscription_status': 'paused',
                },
            },
        }

        with self.cr.savepoint(), patch.object(type(self.account), '_send_dpc_request', ) \
                as mock_send_dpc_request:
            mock_send_dpc_request.return_value = response_with_unknown_status

            subscription_status = self.account.update_subscription_info_for_account()

            self.assertEqual(subscription_status, 'unknown')
            self.assertEqual(self.account.subscription_status, 'unknown')

        response_with_canceled_status = {
            **SUBSCRIPTION_INFO_RESPONSE,
            'data': {
                **SUBSCRIPTION_INFO_RESPONSE['data'],
                'stats': {},
                'subscription_details': {
                    **SUBSCRIPTION_INFO_RESPONSE['data']['subscription_details'],
                    'subscription_status': 'canceled',
                },
            },
        }

        with self.cr.savepoint(), patch.object(type(self.account), '_send_dpc_request', ) \
                as mock_send_dpc_request:
            mock_send_dpc_request.return_value = response_with_canceled_status

            subscription_status = self.account.update_subscription_info_for_account()

            self.assertEqual(subscription_status, 'canceled')
            self.assertEqual(self.account.subscription_status, 'canceled')
            self.assertEqual(self.account.printed, 0)
            self.assertEqual(self.account.limits, 0)

        with self.cr.savepoint(), patch.object(type(self.account), '_send_dpc_request', ) \
                as mock_send_dpc_request:
            mock_send_dpc_request.return_value = {
                'status_code': 404,
                'message': 'Error',
            }

            self.assertFalse(self.account.update_subscription_info_for_account())
            self.assertEqual(self.account.status, 'Error')

        with self.cr.savepoint(), patch.object(type(self.account), '_send_dpc_request', ) \
                as mock_send_dpc_request:
            mock_send_dpc_request.return_value = None

            self.assertFalse(self.account.update_subscription_info_for_account())
            self.assertEqual(self.account.status, 'Failed to fetch subscription info')

        printed = 20
        limits = 110
        self.account.is_dpc_account = False

        with self.cr.savepoint(), patch.object(type(self.account), '_get_limits_printnode', ) \
                as mock_get_limits_printnode:
            mock_get_limits_printnode.return_value = printed, limits

            self.assertFalse(self.account.update_subscription_info_for_account())
            self.assertEqual(self.account.printed, printed)
            self.assertEqual(self.account.limits, limits)
            mock_get_limits_printnode.assert_called_once()

    def test_update_subscription_info(self):
        """
        Test updating subscription information and notification state
        """

        config_parameter = self.env['ir.config_parameter']

        with self.cr.savepoint(), \
                patch.object(type(self.account), 'update_subscription_info_for_account', ) \
                as mock_update_subscription_info_for_account, \
                patch.object(type(self.account), '_notify_about_limits', ) \
                as mock_notify_about_limits, \
                patch.object(type(config_parameter), 'set_param', ) as mock_set_param:
            mock_update_subscription_info_for_account.side_effect = [
                'past_due',
                'active',
            ]

            self.assertIsNone(self.account.update_subscription_info())
            self.assertIsNone(self.account.update_subscription_info())

            self.assertEqual(mock_update_subscription_info_for_account.call_count, 2)
            self.assertEqual(
                mock_set_param.call_args_list,
                [
                    call(
                        'printnode_base.subscription_notification_required',
                        'True',
                    ),
                    call(
                        'printnode_base.subscription_notification_required',
                        'False',
                    ),
                ],
            )
            self.assertEqual(mock_notify_about_limits.call_count, 2)

    def test_notify_about_limits(self):
        """
        Test checking conditions and notifying the customer if limits are close to exceed
        """

        self.company.printnode_notification_email = 'test@email.com'
        self.company.printnode_notification_page_limit = 10
        self.account.limits = 10
        self.account.printed = 0
        mail_template = self.env['mail.template']

        with self.cr.savepoint(), patch.object(type(mail_template), 'send_mail', ) \
                as mock_send_mail:
            self.account.with_company(self.company)._notify_about_limits()
            mock_send_mail.assert_not_called()

            self.account.printed = 5
            self.account.with_company(self.company)._notify_about_limits()
            mock_send_mail.assert_called_once_with(self.company.id, force_send=True)
