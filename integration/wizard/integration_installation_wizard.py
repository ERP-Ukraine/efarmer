# See LICENSE file for full copyright and licensing details.

import os
from urllib.parse import urlparse

import odoo
from odoo import fields, models, _
from odoo.tools.config import DEFAULT_SERVER_WIDE_MODULES


REQUIRED_MODULES = DEFAULT_SERVER_WIDE_MODULES + ['integration', 'integration_queue_job']


class IntegrationInstallationWizard(models.TransientModel):
    _name = 'integration.installation.wizard'
    _description = 'Integration Installation Wizard'

    state = fields.Selection(
        selection=[
            ('step_main', 'Main'),
            ('step_success', 'Success'),
            ('step_error', 'Error'),
        ],
        string='State',
        default='step_main',
    )

    errors = fields.Text(
        string='Errors',
        default='No errors',
    )

    config_template = fields.Text('Configuration Template')

    def _parse_base_url(self):
        """
        Parse the base URL and extract scheme, host, and port.

        Returns:
            tuple: (scheme, base_url, expected_port)
        """
        full_base_url = self.get_base_url()
        parsed_url = urlparse(full_base_url)

        scheme = parsed_url.scheme or 'http'
        base_url = parsed_url.hostname or (parsed_url.netloc.split(':')[0] if parsed_url.netloc else '')

        # Extract port from URL or use protocol defaults
        if parsed_url.port:
            expected_port = parsed_url.port
        elif scheme == 'https':
            expected_port = 443
        else:
            # HTTP default port is 80, not 8069
            # Note: Odoo typically runs on 8069, but if accessed via HTTP without
            # explicit port, it's likely behind a reverse proxy on port 80
            expected_port = 80

        return scheme, base_url, expected_port

    def _is_odoosh_installation(self, base_url):
        """
        Detect if this is an Odoo.sh installation.

        Args:
            base_url (str): The base URL hostname

        Returns:
            bool: True if it's an Odoo.sh installation, False otherwise
        """
        python_path = os.environ.get('PYTHONPATH') or ''
        return '.odoo.com' in base_url or '/odoo.sh' in python_path

    def _check_queue_job_config(self, scheme, base_url, expected_port):
        """
        Check queue_job configuration parameters in odoo.conf.

        Args:
            scheme (str): Expected scheme (http/https)
            base_url (str): Expected hostname
            expected_port (int): Expected port number

        Returns:
            list: List of error messages
        """
        errors = []
        config = odoo.tools.config

        if not os.path.isfile(config.rcfile):
            return errors

        config_params = {
            'queue_job_channels': False,
            'queue_job_scheme': False,
            'queue_job_host': False,
            'queue_job_port': False,
        }

        with open(config.rcfile, 'r') as file:
            for line in file:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Check each queue_job parameter
                for param_name in config_params.keys():
                    if line.startswith(param_name):
                        if config_params[param_name]:
                            errors.append(
                                f'Multiple "{param_name}" parameters found in the "odoo.conf"'
                            )
                        config_params[param_name] = True

                        # Validate the parameter value
                        if '=' in line:
                            param_value = line.split('=', 1)[1].strip()
                            if param_name == 'queue_job_host':
                                # Host should not contain protocol
                                if '//' in param_value:
                                    errors.append(
                                        f'The "{param_name}" parameter in the "odoo.conf" is not set correctly '
                                        f'(should not contain protocol)'
                                    )
                                elif param_value != base_url:
                                    errors.append(
                                        f'The "{param_name}" parameter in the "odoo.conf" is not set correctly '
                                        f'(expected: {base_url})'
                                    )
                            elif param_name == 'queue_job_scheme':
                                if param_value != scheme:
                                    errors.append(
                                        f'The "{param_name}" parameter in the "odoo.conf" is not set correctly '
                                        f'(expected: {scheme})'
                                    )
                            elif param_name == 'queue_job_port':
                                try:
                                    port_value = int(param_value)
                                    if port_value != expected_port:
                                        errors.append(
                                            f'The "{param_name}" parameter in the "odoo.conf" is not set correctly '
                                            f'(expected: {expected_port})'
                                        )
                                except ValueError:
                                    errors.append(
                                        f'The "{param_name}" parameter in the "odoo.conf" is not set correctly '
                                        f'(must be a number)'
                                    )

        # Check for missing parameters
        for param_name, found in config_params.items():
            if not found:
                errors.append(f'The "{param_name}" parameter is not set in the "odoo.conf"')

        return errors

    def _check_server_wide_modules(self):
        """
        Check server-wide modules configuration and build ordered modules string.

        Returns:
            tuple: (errors, modules_str)
                - errors: List of error messages
                - modules_str: Comma-separated string of modules in correct order
        """
        errors = []
        error_necessary_module_msg = 'The necessary module is not set as a server-wide module in the "odoo.conf"'
        config = odoo.tools.config

        # Separate standard modules from custom modules to maintain order
        standard_modules = list(DEFAULT_SERVER_WIDE_MODULES)
        custom_modules = ['integration', 'integration_queue_job']
        required_modules = standard_modules + custom_modules

        server_wide_modules = set(config.options.get('server_wide_modules', []))
        required_modules_set = set(required_modules)

        # Identify missing and extra modules
        missing_required_modules = required_modules_set - server_wide_modules
        extra_required_modules = server_wide_modules - required_modules_set

        # Report errors for missing modules
        if missing_required_modules:
            errors.append(error_necessary_module_msg)

        # Check installed modules
        installed_modules = self.env['ir.module.module'].search([('state', '=', 'installed')])
        integration_modules = installed_modules.filtered(
            lambda m: m.name.startswith('integration_') and 'extension' not in m.name
        )

        integration_modules_list = integration_modules.mapped('name')
        integration_modules_set = set(integration_modules_list)
        missing_integration_modules = integration_modules_set - server_wide_modules

        if missing_integration_modules:
            if error_necessary_module_msg not in errors:
                errors.append(error_necessary_module_msg)

        # Build modules string in correct order: standard modules first, then custom modules
        modules_list = []

        # 1. Add all standard modules (from DEFAULT_SERVER_WIDE_MODULES) in order
        for module in standard_modules:
            modules_list.append(module)

        # 2. Add custom required modules (integration, integration_queue_job)
        for module in custom_modules:
            modules_list.append(module)

        # 3. Add other integration modules (excluding integration and integration_queue_job)
        other_integration_modules = [
            m for m in integration_modules_list
            if m not in custom_modules
        ]
        # Sort for consistency
        other_integration_modules.sort()
        modules_list.extend(other_integration_modules)

        # 4. Add any extra modules that are not standard or integration modules
        extra_modules = [
            m for m in extra_required_modules
            if m not in standard_modules and m not in integration_modules_set
        ]
        # Sort for consistency
        extra_modules.sort()
        modules_list.extend(extra_modules)

        modules_str = ','.join(modules_list)

        return errors, modules_str

    def _build_config_template(self, scheme, base_url, expected_port, is_odoosh, modules_str):
        """
        Build the configuration template for odoo.conf.

        Args:
            scheme (str): URL scheme (http/https)
            base_url (str): Hostname
            expected_port (int): Port number
            is_odoosh (bool): Whether this is an Odoo.sh installation
            modules_str (str): Comma-separated modules string
        """
        server_wide_modules_str = 'server_wide_modules = ' + modules_str + '\n'

        # Build unified configuration template
        config_lines = [
            server_wide_modules_str,
        ]

        # Add workers line only for custom/on-premise servers (not for Odoo.sh)
        if not is_odoosh:
            config_lines.append('workers = 2 ; set here amount of workers higher than 1\n')

        # Add queue_job configuration parameters
        config_lines.extend([
            'queue_job_channels = root:1\n',
            f'queue_job_scheme = {scheme}\n',
            f'queue_job_host = {base_url}\n',
            f'queue_job_port = {expected_port}\n',
        ])

        self.config_template = ''.join(config_lines)

    def check_odoo_setup_for_integration(self):
        """
        Check if the Odoo setup is compatible with the integration.

        This method checks if the Odoo configuration file (odoo.conf) contains the correct
        queue_job configuration parameters (queue_job_channels, queue_job_scheme, queue_job_host,
        queue_job_port), which should match the base URL of the Odoo instance. It also checks if the
        current module is installed as a server-wide module in the Odoo configuration.

        Returns:
            dict: Action dictionary to open the wizard window.
        """
        # Parse base URL
        scheme, base_url, expected_port = self._parse_base_url()

        # Detect installation type
        is_odoosh = self._is_odoosh_installation(base_url)

        # Check queue_job configuration
        errors = self._check_queue_job_config(scheme, base_url, expected_port)

        # Check server-wide modules
        module_errors, modules_str = self._check_server_wide_modules()
        errors.extend(module_errors)

        # Build configuration template and set state
        if errors:
            self._build_config_template(scheme, base_url, expected_port, is_odoosh, modules_str)
            self.errors = ''.join([f'- {e}\n' for e in set(errors)])
            self.state = 'step_error'
        else:
            self.state = 'step_success'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Let\'s ensure a seamless setup!'),
            'res_model': 'integration.installation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def open_configuration_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Getting Started: E-Commerce Connector Made Easy'),
            'res_model': 'integration.configuration.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def close_wizard(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/eci-stores',
            'target': 'self',
        }
