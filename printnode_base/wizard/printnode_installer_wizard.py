# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import requests

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError

from requests.models import PreparedRequest

CONFIGURATION_STEPS = {
    'step_0': 'Introduction',
    'step_1': 'Printing Subscription',
    'step_2': 'Connect Your Print Account',
    'step_3': 'Install the Direct Print Client',
    'step_4': 'Activate Odoo Direct Print PRO',
    'step_5': "Odoo Direct Print PRO has been successfully activated 🎉",
}

URL = 'https://print.api.ventor.tech/printnode-apps'


class PrintnodeInstaller(models.TransientModel):
    """
    Used to set API key to use Direct Print module
    """
    _name = 'printnode.installer'
    _description = 'Direct Print API Key Installer'

    api_key = fields.Char(
        string='API Key',
    )

    state = fields.Selection(
        selection=list(CONFIGURATION_STEPS.items()),
        string='State',
        default='step_0',
    )

    current_step_number = fields.Integer(
        string='Current Step Number',
        default=0,
    )

    is_last_step = fields.Boolean(
        string='Is Last Step?',
        compute='_compute_is_last_step',
        store=False,
        readonly=True,
    )

    company_printnode_enabled = fields.Boolean(
        string="Enable Direct Printing for company",
        default=lambda self: self.env.company.printnode_enabled
    )

    company_printnode_printer = fields.Many2one(
        'printnode.printer',
        string="Default Printer",
        default=lambda self: self.env.company.printnode_printer
    )

    disable_advertising = fields.Boolean(
        string="Disable advertising",
        compute="_compute_disable_advertising",
        store=False
    )

    user_printnode_enabled = fields.Boolean(
        string="Enable Direct Printing for user",
        default=lambda self: self.env.user.printnode_enabled
    )

    user_printnode_printer = fields.Many2one(
        'printnode.printer',
        string="Default Printer (User)",
        default=lambda self: self.env.user.printnode_printer
    )

    client_apps_html = fields.Html(string="Client Apps HTML", default=False, readonly=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        accounts = self.env['printnode.account'].search([]).sorted(key=lambda r: r.id)

        if accounts:
            # First account is main account. All other accounts - not allowed anymore
            # (but will still work for better customer experience)
            account = accounts[0]

            res['api_key'] = account.api_key

        return res

    @api.depends('current_step_number')
    def _compute_is_last_step(self):
        number_of_steps = len(self.__class__.state.selection)

        for record in self:
            record.is_last_step = record.current_step_number == number_of_steps - 1

    def _compute_disable_advertising(self):
        param_value = self.env['ir.config_parameter'].sudo().get_param('printnode_base.disable_advertising', 'False')
        for rec in self:
            rec.disable_advertising = param_value in ('True')

    def action_test_printing(self):
        self.ensure_one()

        printer_id = self.company_printnode_printer or self.user_printnode_printer
        if not printer_id:
            raise UserError("No printer selected for test printing.")

        report_id = self.env.ref('printnode_base.action_report_printnode_test')

        printer_id.printnode_print(
            report_id,
            printer_id,
            copies=1,
            options=None
        )

        return self.go_to_step('step_5')

    def get_api_key(self):
        """
        Redirect the user to the Direct Print Client platform
        """
        portal_base_url = self.env['ir.config_parameter'].sudo().get_param('printnode_base.dpc_url')
        odoo_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        portal_url = f'{portal_base_url}/get-api-key'
        controller_url = f'{odoo_base_url}/dpc-callback'

        # Requests lib used to simplicity
        request = PreparedRequest()
        request.prepare_url(portal_url, {'redirect_url': controller_url})

        return {
            'type': 'ir.actions.act_url',
            'url': request.url,
            'target': 'self',
        }

    def get_client_apps(self):
        for record in self:
            try:
                resp = requests.get(URL, timeout=10)
                resp.raise_for_status()
                apps = resp.json().get("data", [])

                html = ['<div class="border rounded">']

                html.append("""
                    <div class="d-flex justify-content-between bg-secondary bg-gradient
                                align-items-center px-3 py-2 border-bottom fw-bold">
                        <div class="text-start">
                            <strong>OS</strong>
                        </div>
                        <div class="text-center" style="min-width: 90px;">
                            <strong>Link</strong>
                        </div>
                    </div>
                """)

                total = len(apps)
                for i, app in enumerate(apps):
                    os_names = ', '.join(app['supported_os'])
                    border_class = ' border-bottom' if i < total - 1 else ''

                    html.append(f"""
                        <div class="d-flex justify-content-between
                                    align-items-center px-3 py-2{border_class}">
                            <div class="text-start">{os_names}</div>
                            <div class="text-center" style="min-width: 90px;">
                                <a href="{app['url']}" target="_blank"
                                   class="btn btn-outline-primary btn-sm">
                                    Download
                                </a>
                            </div>
                        </div>
                    """)

                html.append('</div>')

                record.client_apps_html = "".join(html)

            except requests.RequestException:
                record.client_apps_html = """
                    <p class='text-danger'>
                        Error loading client apps. Please contact our
                        <a href="https://ventortech.atlassian.net/servicedesk/"
                                "customer/portal/1/group/-1"
                           target="_blank" class="text-decoration-none text-primary">
                            <span class="text-info">support team</span>
                        </a>
                    </p>
                """

    def go_to_step(self, step_name):
        self.state = step_name

        return {
            'type': 'ir.actions.act_window',
            'name': _('Getting Started: %s') % CONFIGURATION_STEPS.get(self.state, 'Welcome to Direct Print PRO!'),  # NOQA
            'res_model': 'printnode.installer',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def go_to_next_step(self):
        if self.is_last_step:
            raise UserError('There is no next step!')

        if self.state == 'step_2':
            self.save_settings()
            self.get_client_apps()

        if self.state == 'step_4':
            self.save_printers_settings()

        self.current_step_number += 1

        return self.go_to_step(f'step_{self.current_step_number}')

    def go_to_prev_step(self):
        if self.current_step_number == 0:
            raise UserError('There is no previous step!')

        self.current_step_number -= 1

        return self.go_to_step(f'step_{self.current_step_number}')

    def go_to_step_0(self):
        self.current_step_number = 0
        return self.go_to_step('step_0')

    def go_to_step_1(self):
        self.current_step_number = 1
        return self.go_to_step('step_1')

    def go_to_step_2(self):
        self.current_step_number = 2
        return self.go_to_step('step_2')

    def go_to_step_3(self):
        self.current_step_number = 3
        return self.go_to_step('step_3')

    def go_to_step_4(self):
        self.current_step_number = 4
        return self.go_to_step('step_4')

    def go_to_step_5(self):
        self.current_step_number = 5
        return self.go_to_step('step_5')

    def save_settings(self):
        if not self.api_key:
            raise exceptions.UserError(_('Please, enter the valid API key'))

        self.env['printnode.account'].update_main_account(self.api_key)

    def save_printers_settings(self):
        # Save to company
        self.env.company.write({
            'printnode_enabled': self.company_printnode_enabled,
            'printnode_printer': self.company_printnode_printer.id,
        })

        # Save to user
        self.env.user.write({
            'printnode_enabled': self.user_printnode_enabled,
            'printnode_printer': self.user_printnode_printer.id,
        })

    def action_finish(self):
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/',
        }
