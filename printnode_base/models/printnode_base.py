# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.tools.misc import str2bool


class PrintnodeBase(models.AbstractModel):
    """ Direct Print Base
    """
    _name = 'printnode.base'
    _description = 'Direct Print Base'

    @api.model
    def get_status(self, only_releases=False):
        """
        Returns all data for status menu.
        """
        if only_releases:
            return {
                'limits': [],
                'devices': {},
                'releases': self.env['printnode.release'].get_releases(),
                'dpc_company_enabled': self.env.company.printnode_enabled,
                'dpc_user_enabled': self.env.user.printnode_enabled,
                'is_advertising_disabled': self._get_advertising_disabled(),
            }

        return {
            'limits': self.env['printnode.account'].get_limits(),
            'devices': [
                ('workstation', self._get_workstation_devices(),),
                ('user', self._get_user_devices(),),
                ('company', self._get_company_devices(),),
            ],
            'releases': self.env['printnode.release'].get_releases(),
            'workstations': self.env['printnode.workstation'].search_read([]),
            'is_advertising_disabled': self._get_advertising_disabled(),
        }

    def _get_advertising_disabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'printnode_base.disable_advertising', 'False'
        )
        return str2bool(param)

    def _get_workstation_devices(self):
        """
        Returns all devices for current workstation.
        """
        return self.env['printnode.workstation'].get_workstation_devices()

    def _get_user_devices(self):
        """
        Returns all devices for current user.

        This method prepare data to the same format as workstation devices
        (get_workstation_devices method).

        Return information about user devices in format:
        [printer, label_printer, scales]
        """
        return [
            {
                'label': _('Default User Printer'),
                'id': self.env.user.printnode_printer.id,
                'name': self.env.user.printnode_printer.name,
            },
            {
                'label': _('Default User Shipping Label Printer'),
                'id': self.env.user.user_label_printer.id,
                'name': self.env.user.user_label_printer.name,
            },
            {
                'label': _('Default User Scales'),
                'id': self.env.user.printnode_scales.id,
                'name': self.env.user.printnode_scales.name,
            },
        ]

    def _get_company_devices(self):
        """
        Returns all devices for current company.

        This method prepare data to the same format as workstation devices
        (get_workstation_devices method).

        Return information about company devices in format:
        [printer, label_printer, scales]
        """
        return [
            {
                'label': _('Default Company Printer'),
                'id': self.env.company.printnode_printer.id,
                'name': self.env.company.printnode_printer.name,
            },
            {
                'label': _('Default Company Shipping Label Printer'),
                'id': self.env.company.company_label_printer.id,
                'name': self.env.company.company_label_printer.name,
            },
            {
                'label': _('Default Company Scales'),
                'id': self.env.company.printnode_scales.id,
                'name': self.env.company.printnode_scales.name,
            },
        ]
