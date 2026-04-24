from odoo import Command, _, api, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        if not self.env.company.x_use_ti:
            return res

        move_ids = self.env['account.move']

        # noinspection PyUnresolvedReferences
        if self.env.context.get('active_model') == 'helpdesk.ticket' and 'move_id' in self.env.context:
            # handle call from helpdesk module
            move_ids = move_ids.browse(self.env.context['move_id'])
            res['move_ids'] = [Command.set(move_ids.ids)]

        return res

    def _prepare_default_reversal(self, move):
        result = super()._prepare_default_reversal(move=move)
        # reverse_date = self.date if self.date_mode == 'custom' else move.date

        if self.env.company.x_use_ti:
            result.update({'ref': self.reason, 'partner_bank_id': move.partner_bank_id.id})

        return result

    def reverse_moves(self, is_modify=False):
        self.ensure_one()

        if self.move_ids.filtered(lambda _am_id: _am_id.is_purchase_document(True)) and self.move_ids.filtered(
            lambda _am_id: _am_id.is_sale_document(True)
        ):
            raise UserError(_('Mixed purchase and sale documents cannot be reversed'))

        if (self.company_id or self.env.company).x_use_ti:
            if is_modify:
                # noinspection PyUnusedLocal
                self = self.with_context(check_move_validity=False)

        return super().reverse_moves(is_modify)
