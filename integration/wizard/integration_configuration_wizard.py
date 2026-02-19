# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


CONFIGURATION_STEPS = {
    'step_0': 'Introduction',
    'step_1': 'Installation and basic Odoo setup',
    'step_2': 'Odoo - E-Commerce store connection configuration',
    'step_3': 'Initial import: master data (attributes, categories, taxes, etc.)',
    'step_4': 'Products: initial import into Odoo',
    'step_5': 'Orders: import configuration & settings',
    'step_6': 'Product information synchronization between E-Commerce store and Odoo',
    'step_7': 'Inventory synchronization: keeping stock updated in E-Commerce store',
    'step_8': 'Congratulations! You\'ve Completed the Setup Wizard 🎉',
}


class IntegrationconfigurationWizard(models.TransientModel):
    _name = 'integration.configuration.wizard'
    _description = 'Integration Configuration Wizard'

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

    is_woocommerce_installed = fields.Boolean(
        string='Is WooCommerce Installed?',
        default=lambda self: self._is_module_installed('integration_woocommerce'),
        store=False,
        readonly=True,
    )

    is_prestashop_installed = fields.Boolean(
        string='Is PrestaShop Installed?',
        default=lambda self: self._is_module_installed('integration_prestashop'),
        readonly=True,
    )

    is_shopify_installed = fields.Boolean(
        string='Is Shopify Installed?',
        default=lambda self: self._is_module_installed('integration_shopify'),
        readonly=True,
    )

    is_magento2_installed = fields.Boolean(
        string='Is Magento 2 Installed?',
        default=lambda self: self._is_module_installed('integration_magento2'),
        store=False,
        readonly=True,
    )

    def go_to_step(self, step_name):
        self.state = step_name

        return {
            'type': 'ir.actions.act_window',
            'name': _('Getting Started: %s') % CONFIGURATION_STEPS.get(self.state, 'E-Commerce Connector Made Easy'),  # NOQA
            'res_model': 'integration.configuration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def go_to_next_step(self):
        if self.is_last_step:
            raise UserError(_('There is no next step!'))

        self.current_step_number += 1

        return self.go_to_step(f'step_{self.current_step_number}')

    def go_to_prev_step(self):
        if self.current_step_number == 0:
            raise UserError(_('There is no previous step!'))

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

    def go_to_step_6(self):
        self.current_step_number = 6
        return self.go_to_step('step_6')

    def go_to_step_7(self):
        self.current_step_number = 7
        return self.go_to_step('step_7')

    def go_to_integrations_list(self):
        action_id = self.env.ref('integration.integrations_list_action').id
        menu_id = self.env.ref('integration.view_sale_integration_kanban').id

        url_menu = '/web#action=%d&model=sale.integration&view_type=kanban&menu_id=%d&cids=1' \
            % (action_id, menu_id)

        return {
            'type': 'ir.actions.act_url',
            'url': url_menu,
            'target': 'self',
        }

    @api.depends('current_step_number')
    def _compute_is_last_step(self):
        number_of_steps = len(self.__class__.state.selection)

        for record in self:
            record.is_last_step = record.current_step_number == number_of_steps - 1

    def _is_module_installed(self, module_name):
        module = self.sudo().env['ir.module.module'].search([('name', '=', module_name)])
        return module and module.state == 'installed'
