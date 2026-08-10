# See LICENSE file for full copyright and licensing details.

import os
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from urllib.parse import urlparse

import odoo
from odoo import fields, models, _
from odoo.tools.config import DEFAULT_SERVER_WIDE_MODULES


REQUIRED_MODULES = DEFAULT_SERVER_WIDE_MODULES + ['integration', 'integration_queue_job']

# The job runner reads its settings from a [queue_job] section of odoo.conf.
# Odoo itself only ever parses the [options] section and logs a warning for every
# key it does not recognise, so settings kept there cost a warning apiece on every
# process start. It never enumerates the other sections, so a section of our own is
# silent -- and it is the same section name OCA's queue_job uses, so this wizard
# validates either module.
QUEUE_JOB_SECTION = 'queue_job'
QUEUE_JOB_KEYS = ('channels', 'scheme', 'host', 'port')

# Odoo stores unknown [options] keys as-is, which is how these used to reach the
# runner. Still honoured there, but they are what Odoo complains about.
LEGACY_PREFIX = 'queue_job_'


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

    def _expected_runner_target(self, is_odoosh):
        """
        Where the job runner should send its "/queue_job/runjob" requests.

        The two platforms genuinely differ here, and the difference is not
        cosmetic.

        On-premise, Odoo binds its own listening socket, so the runner reaches it
        directly on localhost. That also keeps the reverse proxy out of the path:
        routing runjob through it costs a hop and a TLS handshake on every single
        job, and the proxy's own authentication, rate limits or WAF rules can
        reject a request the runner cannot authenticate -- "/queue_job/runjob" is
        an auth="none" route and has no credentials to offer.

        On Odoo.sh the platform's supervisor creates the listening socket and
        hands it to Odoo already bound (socket activation), on the container's
        private address and an ephemeral port that changes on every restart.
        There is no stable internal address to aim at, so the public URL through
        the Odoo.sh router is the only thing that works.

        Args:
            is_odoosh (bool): Whether this is an Odoo.sh installation

        Returns:
            tuple: (scheme, host, port)
        """
        if is_odoosh:
            return self._parse_base_url()

        http_port = odoo.tools.config.get('http_port') or 8069
        return 'http', 'localhost', int(http_port)

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

    def _read_queue_job_settings(self):
        """
        Read the job runner settings out of odoo.conf.

        Returns:
            tuple: (settings, legacy_keys)
                - settings: dict of the [queue_job] section, with any legacy
                  'queue_job_*' key from [options] folded in. The section wins
                  wherever both define a key: it is what the admin wrote most
                  recently, and the legacy key is the one Odoo complains about.
                - legacy_keys: the legacy keys that are still in use, so the
                  caller can tell the user to migrate them.
        """
        config = odoo.tools.config
        cfg_path = config.get('config')

        if not cfg_path or not os.path.isfile(cfg_path):
            return {}, []

        parser = ConfigParser(interpolation=None)
        try:
            parser.read(cfg_path)
        except (OSError, ConfigParserError):
            return {}, []

        settings = {}
        if parser.has_section(QUEUE_JOB_SECTION):
            settings = {
                key: value.strip()
                for key, value in parser[QUEUE_JOB_SECTION].items()
                if value and value.strip()
            }

        legacy_keys = []
        for key in QUEUE_JOB_KEYS:
            value = config.get(f'{LEGACY_PREFIX}{key}')
            if not value:
                continue
            legacy_keys.append(f'{LEGACY_PREFIX}{key}')
            settings.setdefault(key, str(value).strip())

        return settings, legacy_keys

    def _check_queue_job_config(self, scheme, base_url, expected_port, is_odoosh):
        """
        Check the job runner configuration in odoo.conf.

        Args:
            scheme (str): Expected scheme (http/https)
            base_url (str): Expected hostname
            expected_port (int): Expected port number
            is_odoosh (bool): Whether this is an Odoo.sh installation

        Returns:
            list: List of error messages
        """
        errors = []
        settings, legacy_keys = self._read_queue_job_settings()

        if legacy_keys:
            errors.append(_(
                'The job runner is configured through %(keys)s under "[options]" in the '
                '"odoo.conf". These still work, but Odoo logs a warning for each of them '
                'on every restart, because it does not recognise them. Move them into a '
                '"[queue_job]" section instead.',
                keys=', '.join(f'"{key}"' for key in legacy_keys),
            ))

        for key in QUEUE_JOB_KEYS:
            if key not in settings:
                errors.append(_(
                    'The "%(key)s" parameter is not set in the "[queue_job]" section of '
                    'the "odoo.conf".',
                    key=key,
                ))

        # On Odoo.sh the public URL is the only address that reaches Odoo, so it is
        # the only one we accept. Off it, going through the reverse proxy works too
        # and a customer may already be doing exactly that: recommend localhost in
        # the template, but do not call their working setup an error.
        local_hosts = ['localhost', '127.0.0.1']
        public_scheme, public_host, public_port = self._parse_base_url()

        accepted_hosts = [base_url]
        if not is_odoosh:
            accepted_hosts += local_hosts + [public_host]

        host = settings.get('host')
        if host and '//' in host:
            errors.append(_(
                'The "host" parameter in the "odoo.conf" must not contain a protocol '
                '(found: "%(host)s").',
                host=host,
            ))
        elif host and host not in accepted_hosts:
            errors.append(_(
                'The "host" parameter in the "odoo.conf" is not set correctly '
                '(found: "%(host)s", expected: "%(base_url)s").',
                host=host, base_url=base_url,
            ))

        # Scheme and port only mean anything next to the host they sit with: a
        # runner aimed at localhost speaks plain HTTP on Odoo's own port, while one
        # aimed at the public name speaks whatever the proxy in front of it does.
        # So judge them against the host the admin actually chose, not against the
        # one we would have chosen.
        if host and host not in local_hosts:
            scheme, expected_port = public_scheme, public_port

        found_scheme = settings.get('scheme')
        if found_scheme and found_scheme != scheme:
            errors.append(_(
                'The "scheme" parameter in the "odoo.conf" is not set correctly '
                '(found: "%(found)s", expected: "%(scheme)s").',
                found=found_scheme, scheme=scheme,
            ))

        port = settings.get('port')
        if port:
            try:
                port = int(port)
            except ValueError:
                errors.append(_(
                    'The "port" parameter in the "odoo.conf" must be a number '
                    '(found: "%(port)s").',
                    port=port,
                ))
            else:
                if port != expected_port:
                    errors.append(_(
                        'The "port" parameter in the "odoo.conf" is not set correctly '
                        '(found: %(found)s, expected: %(expected)s).',
                        found=port, expected=expected_port,
                    ))

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
        # The job runner settings go in their own [queue_job] section, so they
        # must come after everything that belongs to [options] -- an .ini key
        # after a section header belongs to that section.
        config_lines = [
            'server_wide_modules = ' + modules_str + '\n',
        ]

        # Add workers line only for custom/on-premise servers (not for Odoo.sh)
        if not is_odoosh:
            config_lines.append('workers = 2 ; set here amount of workers higher than 1\n')

        config_lines.extend([
            '\n',
            '; Keep this section at the very end of the file: in an .ini file every\n',
            '; key below a section header belongs to that section, so anything you\n',
            '; put after it stops being an [options] setting.\n',
            f'[{QUEUE_JOB_SECTION}]\n',
            'channels = root:1\n',
            f'scheme = {scheme}\n',
            f'host = {base_url}\n',
            f'port = {expected_port}\n',
        ])

        self.config_template = ''.join(config_lines)

    def check_odoo_setup_for_integration(self):
        """
        Check if the Odoo setup is compatible with the integration.

        This method checks that the "[queue_job]" section of the Odoo configuration file
        (odoo.conf) points the job runner at an address that can actually reach this Odoo,
        which differs between Odoo.sh and on-premise -- see _expected_runner_target(). It
        also checks that the connector is loaded as a server-wide module.

        Returns:
            dict: Action dictionary to open the wizard window.
        """
        # Detect installation type from the public URL, then work out where the
        # job runner should actually send its requests, which is not the same
        # thing on Odoo.sh as it is on-premise.
        __, public_host, __ = self._parse_base_url()
        is_odoosh = self._is_odoosh_installation(public_host)

        scheme, runner_host, expected_port = self._expected_runner_target(is_odoosh)

        # Check queue_job configuration
        errors = self._check_queue_job_config(scheme, runner_host, expected_port, is_odoosh)

        # Check server-wide modules
        module_errors, modules_str = self._check_server_wide_modules()
        errors.extend(module_errors)

        # Build configuration template and set state
        if errors:
            self._build_config_template(scheme, runner_host, expected_port, is_odoosh, modules_str)
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
            'url': '/odoo/eci',
            'target': 'self',
        }
