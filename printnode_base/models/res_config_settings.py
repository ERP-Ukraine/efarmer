# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dpc_api_key = fields.Char(
        string='DPC API Key',
        related='printnode_account_id.api_key',
        readonly=False,
    )

    dpc_status = fields.Char(
        string='Direct Print Client API Key Status',
        related='printnode_account_id.status',
    )

    dpc_is_scales_debug_enabled = fields.Boolean(
        string="Enable scales debug",
        related='printnode_account_id.is_scales_debug_enabled',
        readonly=True,
    )

    printnode_account_id = fields.Many2one(
        comodel_name='printnode.account',
        compute='_compute_printnode_account_id',
        readonly=True,
        compute_sudo=True,
    )

    disable_advertising = fields.Boolean(
        string="Disable advertising",
        config_parameter='printnode_base.disable_advertising',
    )

    def _compute_printnode_account_id(self):
        account = self.env['printnode.account'].get_main_printnode_account()
        for settings in self:
            settings.printnode_account_id = account

    @api.onchange('group_stock_tracking_lot')
    def _onchange_group_stock_tracking_lot(self):
        """
        Disable the "Print Package Label Immediately After Shipping Label" setting
        if the user disables the "Packages" setting
        """
        if not self.group_stock_tracking_lot and self.env.company.print_package_with_label:
            self.env.company.print_package_with_label = False

            return {
                'warning': {
                    'title': _("Warning!"),
                    'message': _(
                        'Disabling this option will also automatically disable option '
                        '"Print Package Label Immediately After Shipping Label" in Direct Print settings'
                    ),
                }
            }

    # Buttons

    # TODO: Perhaps this concept should be reconsidered, because there can be two or more
    #  accounts. In this case, actions like ('activate_account', 'import_devices',
    #  'clear_devices_from_odoo', ...) must be performed not for the main account with
    #  index [0], but for the account that is selected in the "dpc_api_key" field!
    def get_main_printnode_account(self):
        return self.env['printnode.account'].get_main_printnode_account()

    def activate_account(self):
        """
        Callback for activate button. Finds and activates the main account
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(_('Please add an account before activation'))

        return account.activate_account()

    def import_devices(self):
        """ Import Printers & Scales button in Settings.
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(_('Please, add an account before importing printers'))

        return account.import_devices()

    def clear_devices_from_odoo(self):
        """ Callback for "Clear Devices from Odoo" button.
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(_('Please add an account before clearing devices'))

        return account.clear_devices_from_odoo()

    def enable_scales_debug_mode(self):
        """
        Create a test scale with computer
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(
                _('Please add an account before enabling test scales integration'))

        return account.enable_scales_debug_mode()

    def disable_scales_debug_mode(self):
        """
        Delete test scale with computer
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(
                _('Please add an account before disabling test scales integration'))

        return account.disable_scales_debug_mode()

    def generate_debug_scales_measurement(self):
        """
        Generate a test measurement for the test scale
        """
        account = self.get_main_printnode_account()

        if not account:
            raise exceptions.UserError(
                _('Please add an account before generating a test measurement'))

        return account.generate_debug_scales_measurement()

    def open_current_company(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Company",
            "res_model": "res.company",
            "view_mode": "form",
            "target": "current",
            "res_id": self.company_id.id,
        }
