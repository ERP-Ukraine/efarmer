import re

import requests
from stdnum import iban, pl

from odoo import _, fields, models, release


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_wl_error_type = fields.Char(string='Error Type')
    x_wl_error_message = fields.Char(string='Error Message')

    def _x_wl_validate_bank_account(self):
        errors = {}
        for invoice_id in self:
            if not invoice_id.commercial_partner_id:
                errors[invoice_id.id] = {'error_type': 'invalid_vat', 'error_message': _('Select Partner first!')}
                continue

            if not invoice_id.commercial_partner_id.vat:
                errors[invoice_id.id] = {
                    'error_type': 'invalid_vat',
                    'error_message': _('Partner is missing VAT number!'),
                }
                continue

            vat = re.sub(r'\D', '', invoice_id.commercial_partner_id.vat)

            if not pl.nip.is_valid(vat):
                errors[invoice_id.id] = {
                    'error_type': 'invalid_vat',
                    'error_message': _('Partner VAT number is missing or is incorrect!'),
                }
                continue

            acc_number = re.sub(r'\D', '', invoice_id.partner_bank_id.sanitized_acc_number or '')

            if not acc_number or len(acc_number) != 26 or not iban.is_valid(f'PL{acc_number}'):
                errors[invoice_id.id] = {
                    'error_type': 'invalid_bank_acc',
                    'error_message': _('Partner account number is missing or is incorrect!'),
                }
                continue

            response = requests.get(
                f'https://wl-api.mf.gov.pl/api/check/nip/{vat}/bank-account/{acc_number}',
                params={'date': fields.Date.today().isoformat()},
                headers={'user-agent': f'{release.description} {release.version}'},
            )

            if response.ok:
                result = response.json()
                if 'result' in result:
                    if result['result']['accountAssigned'].upper() == 'TAK':
                        message = _(
                            'POSITIVE whitelist validation status, request id: %s.', result['result']['requestId']
                        )
                        invoice_id.message_post(body=message)
                        errors[invoice_id.id] = {'error_type': 'positive', 'error_message': message}
                    else:
                        message = _(
                            'NEGATIVE whitelist validation status, request id: %s.', result['result']['requestId']
                        )
                        invoice_id.message_post(body=message)
                        errors[invoice_id.id] = {'error_type': 'negative', 'error_message': message}
                else:
                    errors[invoice_id.id] = {
                        'error_type': 'api_error',
                        'error_message': _('Error from MF API: %s', result.get('exception')),
                    }
            else:
                errors[invoice_id.id] = {
                    'error_type': 'api_error',
                    'error_message': _(
                        'Error accessing MF API: [%s] %s',
                        response.status_code,
                        response.reason or response.json().get('message', ''),
                    ),
                }

        return errors

    def x_wl_action_validate_bank_account(self):
        errors = self._x_wl_validate_bank_account()

        if self.env.context.get('no_confirm', False) and not errors:
            return {}

        record_id = (
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

        return {
            'name': _('Whitelist Check Results'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'trilab.check.wl',
            'res_id': record_id.id,
            'target': 'new',
        }
