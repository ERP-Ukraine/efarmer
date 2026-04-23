from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_partner_is_europe = fields.Boolean(related='partner_id.x_pl_is_europe')

    def x_pl_check_vies(self):
        self.ensure_one()
        result = self.partner_id.x_pl_check_vies()

        if result[self.partner_id.id].get('error_type') == 'vies_ok':
            message = _('Valid VIES') if self.partner_id.x_pl_vies_state == 'valid' else _('Invalid VIES')
            if response_id := result[self.partner_id.id].get('response_id'):
                message += _(', id: %s', response_id)
            self.message_post(body=message)
