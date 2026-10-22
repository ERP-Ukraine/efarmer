# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import logging
import re
import requests
import time

from odoo import api, exceptions, fields, models, _

from .constants import Constants
from ..tools import convert_iso_to_date

_logger = logging.getLogger(__name__)


# Retry configuration for PrintNode API rate limiting
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # Base delay in seconds for exponential backoff
SUPPORTED_SUBSCRIPTION_STATUSES = {
    'incomplete',
    'incomplete_expired',
    'trialing',
    'active',
    'past_due',
    'canceled',
    'unpaid',
}

# Copied from request library to provide compatibility with the library
try:
    from simplejson import JSONDecodeError
except ImportError:
    from json import JSONDecodeError


class PrintNodeAccount(models.Model):
    """ Direct Print Account entity
    """
    _name = 'printnode.account'
    _inherit = 'printnode.logger.mixin'
    _description = 'Direct Print Account'

    name = fields.Char(
        string='Name',
        default='Default Account',
    )

    alias = fields.Char(
        string='Alias'
    )

    api_key = fields.Char(
        string='API Key',
        required=True
    )

    password = fields.Char(
        string='Password',
        required=False
    )

    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        readonly=True,
        default='https://api.printnode.com'
    )

    printnode_id = fields.Integer('Account ID')

    is_dpc_account = fields.Boolean(
        "Is Direct Print Client Account",
        default=False,
    )

    status = fields.Char(
        string='Status',
        compute='_compute_account_status',
        store=True,
        readonly=True
    )

    subscription_plan = fields.Char(
        string='Printing Plan',
        readonly=True,
    )

    subscription_status = fields.Selection(
        [
            ('incomplete', 'Incomplete'),
            ('incomplete_expired', 'Incomplete Expired'),
            ('trialing', 'Trialing'),
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('canceled', 'Canceled'),
            ('unpaid', 'Unpaid'),
            ('unknown', 'Unknown'),
        ],
        string='Subscription Status',
        readonly=True,
    )

    subscription_start_date = fields.Date(
        string='Subscription Start Date',
        readonly=True,
    )

    subscription_end_date = fields.Date(
        string='Subscription End Date',
        readonly=True,
    )

    limits = fields.Integer(
        string='Plan Page Limits',
        readonly=True,
    )

    printed = fields.Integer(
        string='Printed',
        readonly=True,
    )

    computer_ids = fields.One2many(
        'printnode.computer',
        'account_id',
        string='Computers'
    )

    is_scales_debug_enabled = fields.Boolean(
        "Is Scales Debug Enabled",
        default=False,
    )

    _unique_printnode_id = models.Constraint(
        'UNIQUE(printnode_id)',
        'Account already exists.',
    )

    _unique_api_key = models.Constraint(
        'UNIQUE(api_key)',
        'API Key (token) must be unique.',
    )

    @api.depends('endpoint', 'api_key', 'password')
    def _compute_account_status(self):
        """
        Request Direct Print account details - whoami
        """
        for rec in self.filtered(lambda x: x.endpoint and x.api_key):
            rec._send_printnode_request('whoami')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'endpoint' in vals:
                vals['endpoint'] = self._normalize_endpoint(vals['endpoint'])

        account = super(PrintNodeAccount, self).create(vals_list)

        if account and not self.env.context.get('skip_device_import'):
            account.import_devices()

        return account

    def write(self, vals):
        activate_account = False

        if 'endpoint' in vals:
            vals['endpoint'] = self._normalize_endpoint(vals['endpoint'])

        if 'api_key' in vals:
            # When API Key changed - activate the account
            if vals['api_key'] != self.api_key:
                activate_account = True

        res = super(PrintNodeAccount, self).write(vals)

        if activate_account:
            self.activate_account(reconcile_devices=True)

        return res

    @staticmethod
    def _normalize_endpoint(endpoint):
        return endpoint.rstrip('/') if endpoint else endpoint

    def update_main_account(self, api_key):
        """
        Update an existing or create a new main account.
        The main account is the account with lowest ID.
        """
        main_account = self.get_main_printnode_account()

        if main_account:
            if not api_key:
                # Remove account
                main_account.unlink()
            else:
                # Update account
                if main_account.api_key != api_key:
                    main_account.api_key = api_key

        else:
            if api_key:
                # Activation imports devices once the key is verified, so importing on create
                # would fetch them twice and delete the first import
                main_account = self.env['printnode.account'].with_context(
                    skip_device_import=True,
                ).create({
                    'api_key': api_key,
                })
                main_account.activate_account()

        return main_account

    def get_main_printnode_account(self):
        """
        The main account is the account with lowest ID.
        """
        accounts = self.env['printnode.account'].search([]).sorted(key=lambda r: r.id)

        return accounts[0] if accounts else False

    def activate_account(self, reconcile_devices=False):
        """
        Activate the current account through the DPC service with the API Key provided.

        :param bool reconcile_devices: Keep existing devices and remove only devices absent
            from the Direct Print account. Otherwise delete all devices and import them again.
        """
        base_module = self.env['ir.module.module'].search([['name', '=', 'base']])
        odoo_version = base_module.latest_version.split('.')[0]

        params = {
            "type": "odoo",
            "version": odoo_version,
            "identifier": self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            "action": "activate"
        }

        # Activate through DPC service
        response = self._send_dpc_request('PUT', f'api-key-activations/{self.api_key}', json=params)

        # Any request errors
        if not response:
            # No response means that DPC API is not responding or something went wrong.
            # It is better to try activate through Direct Print API instead of activation error

            # We do not know for sure
            self.is_dpc_account = None

            # But can try to activate through Direct Print
            if self._is_correct_dpc_api_key():
                self.update_subscription_info_for_account()
                self._update_devices(reconcile_devices)

                return

            raise exceptions.UserError(
                _(
                    'Wrong API Key provided. Please, provide the correct key or '
                    'check Direct Print PRO / Settings page for details.\n\n'
                    'Error details: {}'
                ).format(self.status)
            )

        # Everything is okay: the key is from DPC
        if response.get('status_code', 200) == 200:
            self.is_dpc_account = True
            self.update_subscription_info_for_account()
            self._update_devices(reconcile_devices)

            return

        # Status 404 means that it can be Direct Print API Key but we do not have it in DPC DB
        # User can provide Direct Print API key (with no use of our service)
        if response.get('status_code', 200) == 404:
            self.is_dpc_account = False

            if self._is_correct_dpc_api_key():
                self.update_subscription_info_for_account()
                self._update_devices(reconcile_devices)

                return

        # Something is wrong with the key
        self.status = response.get('message', 'Something went wrong')

        raise exceptions.UserError(
            _(
                'Wrong API Key provided. Please, provide the correct key or '
                'check Direct Print / Settings page for details.\n\n'
                'Error details: {}'
            ).format(self.status)
        )

    def _is_correct_dpc_api_key(self):
        """
        Checks whether API key related to Direct Print account
        """
        response = self._send_printnode_request('whoami')
        return bool(response)

    def _update_devices(self, reconcile_devices):
        if reconcile_devices:
            self.clear_devices_from_odoo()
        else:
            self.unlink_devices()
            self.import_devices()

    def import_devices(self):
        """
        Import devices after fetching all computers and printers successfully.
        """
        devices = self._fetch_remote_inventory()
        self._apply_devices(devices)

    def clear_devices_from_odoo(self):
        """
        Import devices, then delete computers and printers absent from the remote inventory.
        """
        devices = self._fetch_remote_inventory()
        self._apply_devices(devices)

        computer_ids = set()
        printer_ids = set()
        for computer in devices:
            computer_ids.add(computer['id'])
            for printer in computer['printers']:
                printer_ids.add(printer['id'])

        computers_to_delete = self.with_context(active_test=False).computer_ids.filtered(
            lambda computer: computer.printnode_id not in computer_ids
        )
        printers_to_delete = self.env['printnode.printer'].sudo().with_context(active_test=False).search([
            ('account_id', '=', self.id),
        ]).filtered(
            lambda printer: printer.printnode_id not in printer_ids
            or printer.computer_id in computers_to_delete
        )

        for model in ['printnode.scenario', 'delivery.carrier', 'printnode.action.button']:
            self.env[model].sudo().with_context(active_test=False).search([
                ('printer_id', 'in', printers_to_delete.ids),
            ]).write({'printer_id': False})

        printers_to_delete.unlink()
        computers_to_delete.unlink()

    def unlink_devices(self):
        """
        Delete computers, printers, print jobs and user rules
        """
        for computer in self.with_context(active_test=False).computer_ids:
            for rule in self.env['printnode.rule'].search([
                ('printer_id', 'in', computer.printer_ids.ids),
            ]):
                rule.unlink()
            for printer in computer.printer_ids:
                for job in printer.printjob_ids:
                    job.unlink()
                printer.unlink()
            computer.unlink()

    def _fetch_remote_inventory(self):
        """
        Fetch the complete list of computers and printers, with available scales readings.
        """
        self.ensure_one()
        devices = []
        for computer in self._get_all_computers():
            printers = self._get_all_printers(computer['id'])
            scales = self._get_scales_or_empty(computer['id'])
            devices.append({**computer, 'printers': printers, 'scales': scales})
        return devices

    def _get_all_computers(self):
        return self._request_all_pages('computers')

    def _get_all_printers(self, computer_id):
        return self._request_all_pages(f'computers/{computer_id}/printers')

    def _get_scales_or_empty(self, computer_id):
        """
        Get current scales readings of a computer, skipping incomplete ones.
        Return an empty list if the request fails, so scales never block device sync.
        """
        scales = self._send_printnode_request(f'computer/{computer_id}/scales')
        if not isinstance(scales, list):
            return []

        required_fields = {'productId', 'deviceName', 'deviceNum'}
        return [
            scale for scale in scales
            if isinstance(scale, dict) and required_fields.issubset(scale)
        ]

    def _request_all_pages(self, uri):
        """
        Request all pages of a device list.
        Raise on an invalid or duplicate device: a malformed response must not reach import or cleanup.
        """
        devices = []
        device_ids = set()
        params = {'limit': 100}

        while True:
            resp = self._request_device_page(uri, params=params)
            for device in resp:
                if (
                    not isinstance(device, dict)
                    or not {'id', 'name', 'state'}.issubset(device)
                    or type(device['id']) is not int
                    or device['id'] <= 0
                    or device['id'] in device_ids
                ):
                    raise exceptions.UserError(_(
                        'Invalid device response from Direct Print. Please try again.'
                    ))
                device_ids.add(device['id'])
            devices.extend(resp)

            if len(resp) < params['limit']:
                break

            params = {**params, 'after': resp[-1]['id']}

        return devices

    def _request_device_page(self, uri, params=None):
        """
        An empty list is valid; a failed request is not an empty inventory.
        """
        response = self._send_printnode_request(uri, params=params)
        if not isinstance(response, list):
            raise exceptions.UserError(_('Could not fetch devices from Direct Print. Please try again.'))
        return response

    def _apply_devices(self, computers):
        """
        Create or update computers, printers and scales from the remote inventory.
        Existing records are updated in place to preserve printing settings.
        """
        self._deactivate_scales()
        for computer in computers:
            odoo_computer = self._get_node('computer', computer, self.id)

            # Downloading printers with tray bins
            for printer in computer['printers']:
                odoo_printer = self._get_node('printer', printer, odoo_computer.id)

                capabilities = printer.get('capabilities') or {}
                bins = capabilities.get('bins') or []
                for bin_name in bins:
                    self._create_printer_bin(bin_name, odoo_printer)

            # Downloading scales
            for scales in computer['scales']:
                self._create_or_update_scales(scales, odoo_computer)

    def _get_node(self, node_type, node_data, parent_id):
        """
        Create or update a computer or printer by its Direct Print ID.
        Archived records are matched too, since printnode_id is unique.
        """
        node = self.env[f'printnode.{node_type}'].with_context(active_test=False).search([
            ('printnode_id', '=', node_data['id']),
        ], limit=1)

        vals = {
            'name': node_data['name'],
            'status': node_data['state'],
        }
        if node_type == 'printer':
            vals['computer_id'] = parent_id

        if node:
            node.write(vals)
        else:
            vals['printnode_id'] = node_data['id']
            if node_type == 'computer':
                vals['account_id'] = parent_id
            node = node.create(vals)

        return node

    def _create_printer_bin(self, bin_name, odoo_printer):
        existing_bin = self.env['printnode.printer.bin'].search(
            [('name', '=', bin_name), ('printer_id', '=', odoo_printer.id)],
            limit=1,
        )
        if not existing_bin:
            self.env['printnode.printer.bin'].create({
                'name': bin_name,
                'printer_id': odoo_printer.id,
            })

    def _create_or_update_scales(self, scales, odoo_computer):
        scales_env = self.env['printnode.scales']
        existing_scales = scales_env.with_context(active_test=False).search([
            ('printnode_id', '=', scales['productId']),
            ('computer_id', '=', odoo_computer.id)
        ], limit=1)

        vals = {
            'name': scales['deviceName'],
            'device_num': scales['deviceNum'],
            'status': 'online',
        }
        if existing_scales:
            existing_scales.write(vals)
        else:
            vals.update({
                'printnode_id': scales['productId'],
                'computer_id': odoo_computer.id,
            })
            scales_env.create(vals)

    def recheck_printer(self, printer, print_sample_report=False):
        """
        Re-check particular printer status
        """
        uri = f'printers/{printer.printnode_id}'

        resp = self._send_printnode_request(uri)

        if resp:
            printer_status = resp[0].get('state', 'offline')
            computer_status = resp[0]['computer'].get('state', 'disconnected')

            if printer.status != printer_status:
                printer.status = printer_status

            if printer.computer_id.status != computer_status:
                printer.computer_id.status = computer_status

        return printer.online

    def _deactivate_printers(self):
        """
        Deactivate printers only from current account
        """
        self.ensure_one()

        domain = [['computer_id', 'in', self.computer_ids.ids]]
        self.env['printnode.printer'].with_context(active_test=False)\
            .search(domain).write({'status': 'offline'})

    def _deactivate_scales(self):
        """
        Mark scales from the current account offline, including archived scales.
        """
        self.ensure_one()
        self.env['printnode.scales'].with_context(active_test=False).search([
            ('account_id', '=', self.id),
        ]).write({'status': 'offline'})

    @api.model
    def run_maintenance(self):
        """
        Run Direct Print maintenance tasks.

        Each maintenance action is isolated in a savepoint, so a failed action
        does not block the next maintenance actions.
        """
        def run_action(action_name, action_method, *args, **kwargs):
            try:
                with self.env.cr.savepoint():
                    action_method(*args, **kwargs)
            except Exception as err:
                _logger.exception(
                    'Direct Print Maintenance: action "%s" failed with error: %s',
                    action_name,
                    err,
                )

        run_action(
            'update_subscription_info',
            self.env['printnode.account'].update_subscription_info,
        )
        run_action(
            'update_releases',
            self.env['printnode.release'].update_releases,
        )
        run_action(
            'clean_printjobs',
            self.env['printnode.printjob'].clean_printjobs,
            older_than_days=15,
        )

    @api.model
    def update_subscription_info(self):
        """
        Update limits and subscription info through API.
        """
        main_account = self.get_main_printnode_account()

        for rec in self.env['printnode.account'].search([]):
            subscription_status = rec.update_subscription_info_for_account()

            if subscription_status and rec == main_account:
                self.env['ir.config_parameter'].sudo().set_param(
                    'printnode_base.subscription_notification_required',
                    'True' if subscription_status == 'past_due' else 'False',
                )

        self._notify_about_limits()

    def update_subscription_info_for_account(self):
        """
        Update limits and subscription info through API.
        """
        self.ensure_one()

        if self.is_dpc_account:
            if not self.api_key:
                return False

            response = self._send_dpc_request(
                'GET',
                'api-keys',
                headers={'DPC-API-Key': self.api_key},
            )

            if not response:
                message = _('Failed to fetch subscription info')
                self.status = message
                _logger.warning(
                    'Failed to update subscription info for account "%s": %s',
                    self.name,
                    message,
                )
                return False

            if response.get('status_code') != 200:
                message = response.get('message', _('Something went wrong'))
                self.status = message
                _logger.warning(
                    'Failed to update subscription info for account "%s": %s',
                    self.name,
                    message,
                )
                return False

            data = response.get('data') or {}
            stats = data.get('stats') or {}
            subscription_details = data.get('subscription_details') or {}

            subscription_status = subscription_details.get('subscription_status')
            if subscription_status not in SUPPORTED_SUBSCRIPTION_STATUSES:
                subscription_status = 'unknown'

            self.write({
                'printed': stats.get('printed') or 0,
                'limits': stats.get('limits') or 0,
                'subscription_status': subscription_status,
                'subscription_plan': subscription_details.get('subscription_plan') or False,
                'subscription_start_date': convert_iso_to_date(
                    subscription_details.get('subscription_start_date')
                ),
                'subscription_end_date': convert_iso_to_date(
                    subscription_details.get('subscription_end_date')
                ),
            })

            return subscription_status

        printed, limits = self._get_limits_printnode()

        self.printed = printed
        self.limits = limits

        return False

    def _get_limits_printnode(self):
        """
        Get limits (printed pages + total available pages) from Direct Print through API
        """
        printed = 0
        limits = 0

        stats = self._send_printnode_request('billing/statistics')

        # Unavailable for child Direct Print accounts
        if stats and 'current' in stats:
            printed = stats['current'].get('prints', 0)

        plan = self._send_printnode_request('billing/plan')

        # Unavailable for child Direct Print accounts
        if plan and 'current' in plan:
            raw_limits = plan['current'].get('printCurve')
            if raw_limits:
                # Parse with regex value like '("{0,5000}","{0,0}",0.0018)
                match = re.match(r'\(\"{(?P<_>\d+),(?P<limits>\d+)}\",.*\)', raw_limits)
                limits = (match and match.group('limits')) or 0

        return printed, limits

    def _notify_about_limits(self):
        """
        Check conditions and notify the customer if limits are close to exceed
        """
        company = self.env.company

        if company.printnode_notification_email and company.printnode_notification_page_limit:
            accounts_to_notify = self.env['printnode.account'].search([]).filtered(
                lambda r: r.limits > 0
                    and (r.limits - r.printed) < company.printnode_notification_page_limit)  # NOQA

            if accounts_to_notify:
                context = self.env.context.copy()
                context.update({'accounts': accounts_to_notify})

                mail_template = self.env.ref('printnode_base.reaching_limit_notification_email')
                mail_template.with_context(**context).send_mail(company.id, force_send=True)

    @api.model
    def get_limits(self):
        """
        Get print limits for the current account.

        This is used to display information about the limits of the current account on UI
        in the main menu of the Printnod.
        """
        limits = []
        for rec in self.env['printnode.account'].search([]):
            if rec.status == 'OK':
                limits.append({
                    'account': rec.name or rec.api_key[:10] + '...',
                    'printed': rec.printed,
                    'limits': rec.limits,
                })
            else:
                limits.append({
                    'account': rec.name or rec.api_key[:10] + '...',
                    'error': rec.status,
                })
        return limits

    def enable_scales_debug_mode(self):
        """
        Enable debug mode for scales: this includes creation of test scales and
        showing a button to generate test measurements
        """
        self.ensure_one()

        # Create a new test computer
        test_computer = self.env['printnode.computer'].create({
            'name': 'Computer with test scales',
            'printnode_id': 0,
            'account_id': self.id,
        })

        # Create a new test scales connected to the test computer
        self.env['printnode.scales'].create({
            'name': 'PrintNode Test Scale',
            'printnode_id': 0,
            'device_num': 0,
            'computer_id': test_computer.id,
            'account_id': self.id,
        })

        # Update flag
        self.is_scales_debug_enabled = True

    def disable_scales_debug_mode(self):
        """
        Disable debug mode for scales: this includes deletion of test scales and
        test computer
        """
        self.ensure_one()

        # Delete test computer
        self.computer_ids.filtered(lambda c: c.printnode_id == 0).unlink()

        # Update flag
        self.is_scales_debug_enabled = False

    def generate_debug_scales_measurement(self):
        """
        Generate a debug measurement for all scales connected to the current
        account
        """
        self.ensure_one()

        self._send_printnode_request('scale', method='PUT')

        return True

    def _send_printnode_request(self, uri, params=None, method='GET'):
        """
        Send request with basic authentication and API key
        """
        auth = requests.auth.HTTPBasicAuth(self.api_key, self.password or '')
        request_url = f'{self.endpoint}/{uri}'

        for attempt in range(MAX_RETRIES + 1):
            try:
                self.printnode_logger(
                    Constants.REQUESTS_LOG_TYPE,
                    f'{method} request: {request_url}'
                )

                resp = self._get_requests_method(method)(
                    request_url, params=params, auth=auth, timeout=20
                )

                # Retry logic for rate limiting
                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        self._handle_retry(attempt, 'Rate limited (429)')
                        continue
                    return

                # 403 is a HTTP status code which can be returned for child accounts in some cases
                # like checking printing limits on Direct Print
                if resp.status_code not in (200, 204, 403):
                    resp.raise_for_status()

                if self.status != 'OK':
                    self.status = 'OK'

                if not resp.text:
                    # Some requests return empty response, it's not an error
                    self.printnode_logger(
                        Constants.REQUESTS_LOG_TYPE,
                        f'Response from ({request_url}): {resp.status_code}'
                    )
                    return

                json_response = resp.json()

                self.printnode_logger(
                    Constants.REQUESTS_LOG_TYPE,
                    f'Response from ({request_url}): {json_response}'
                )

                return json_response

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.RequestException,
            ) as err:
                # Deactivate printers only from current account
                self._deactivate_printers()

                self.status = err

                if isinstance(err, requests.exceptions.Timeout):
                    error_message = 'Request timed out'
                elif isinstance(err, requests.exceptions.ConnectionError):
                    error_message = f'ConnectionError: {err}'
                else:
                    error_message = f'RequestException: {err}'

                self.printnode_logger(Constants.REQUESTS_LOG_TYPE, error_message)

                if attempt < MAX_RETRIES:
                    self._handle_retry(attempt, error_message)
                    continue

            return None

    def _handle_retry(self, attempt, reason):
        """
        Log retry reason and wait before the next attempt.
        """
        delay = RETRY_DELAY_BASE * (2 ** attempt)
        self.printnode_logger(
            Constants.REQUESTS_LOG_TYPE,
            f'{reason}. Retrying in {delay} seconds '
            f'(retry {attempt + 1}/{MAX_RETRIES})'
        )
        time.sleep(delay)

    def _send_dpc_request(self, method, uri, **kwargs):
        """
        Send request to DPC API with API key
        """
        dpc_url = self.env['ir.config_parameter'].sudo().get_param('printnode_base.dpc_api_url')

        try:
            resp = self._get_requests_method(method)(f'{dpc_url}/{uri}', **kwargs)

            if self.status != 'OK':
                self.status = 'OK'

            json_resp = resp.json()
            self.printnode_logger(
                Constants.REQUESTS_LOG_TYPE,
                f'Response from ({dpc_url}): {json_resp}'
            )
            return json_resp
        except requests.exceptions.ConnectionError as err:
            self._deactivate_printers()

            self.status = err
            self.printnode_logger(Constants.REQUESTS_LOG_TYPE, f'ConnectionError: {err}')
        except requests.exceptions.RequestException as err:
            self._deactivate_printers()

            self.status = err
            self.printnode_logger(Constants.REQUESTS_LOG_TYPE, f'RequestException: {err}')
        except JSONDecodeError as err:
            self._deactivate_printers()

            self.status = err
            self.printnode_logger(Constants.REQUESTS_LOG_TYPE, f'JSONDecodeError: {err}')

        return None

    def _get_requests_method(self, method):
        methods = {
            'GET': requests.get,
            'POST': requests.post,
            'PUT': requests.put,
        }

        if method not in methods:
            raise ValueError('Bad HTTP method')

        return methods[method]
