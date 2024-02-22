# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    whitelist_history_ids = fields.One2many(
        comodel_name='whitelist.history',
        inverse_name='account_id',
        string='White Lists'
    )

    def x_wl_action_validate_bank_account(self):
        errors = self._x_wl_validate_bank_account()

        if self.env.context.get('no_confirm', False) and not errors:
            return {}

        record = (
            self.env['trilab.check.wl']
            .sudo()
            .create(
                {
                    'check_ids': [
                        fields.Command.create(
                            {
                                'invoice_id': inv.id,
                                'error_type': errors.get(inv.id, {}).get('error_type'),
                                'error_message': errors.get(inv.id, {}).get('error_message'),
                            }
                        )
                        for inv in self
                    ]
                }
            )
        )

        for inv_record in self:
            self.env['whitelist.history'].create({
                'name': '{} WhiteList History'.format(str(inv_record.id)),
                'token': errors.get(inv_record.id, {}).get('request id') or ''.join(errors.get(inv_record.id, {}).get('error_message').replace('.', '').split('id: ')[1:]),
                'invoice_number': inv_record.name,
                'message': errors.get(inv_record.id, {}).get('error_message'),
                'account_id': inv_record.id,
            })

        return {
            'name': _('Whitelist Check Results'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'trilab.check.wl',
            'res_id': record.id,
            'target': 'new',
        }

