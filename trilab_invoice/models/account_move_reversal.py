# noinspection PyProtectedMember
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    selected_correction_invoice = fields.Many2one('account.move')
    x_is_poland = fields.Boolean(compute='_x_compute_is_poland', string='Technical Field: Is Poland')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # can't use x_is_poland as self is not instantiated yet
        if self.env.company.country_id.id != self.env.ref('base.pl').id:
            return res

        move_ids = self.env['account.move']

        # noinspection PyUnresolvedReferences
        if self.env.context.get('active_model') == 'helpdesk.ticket':
            move_ids = move_ids.browse([self.env.context.get('move_id')])

        elif 'active_ids' in self.env.context:
            if len(self.env.context['active_ids']) > 1:
                raise ValidationError(_('Single invoice only'))

            move_ids = move_ids.browse(self.env.context['active_ids'])

        if move_ids:
            if move_ids.move_type in ['in_refund', 'out_refund']:
                res['selected_correction_invoice'] = move_ids.id
                move_ids = move_ids.refund_invoice_id

            res['refund_method'] = 'cancel' if move_ids.move_type == 'entry' else 'refund'
            res['residual'] = move_ids.amount_residual
            res['currency_id'] = move_ids.currency_id.id if move_ids.currency_id else False
            res['move_type'] = move_ids.move_type

        return res

    def _x_compute_is_poland(self):
        for rec in self:
            rec.x_is_poland = rec.env.company.country_id.id == rec.env.ref('base.pl').id

    @api.depends('move_ids')
    def _compute_from_moves(self):
        if not any(self.mapped('x_is_poland')):
            # noinspection PyProtectedMember
            return super()._compute_from_moves()

        for record in self:
            move_ids = record.move_ids
            if self.selected_correction_invoice:
                move_ids = self.selected_correction_invoice.refund_invoice_id.id
            if isinstance(move_ids, int):
                move_ids = self.env['account.move'].browse(move_ids)
            record.residual = len(move_ids) == 1 and move_ids.amount_residual or 0
            record.currency_id = len(move_ids.currency_id) == 1 and move_ids.currency_id or False
            record.move_type = (
                move_ids.move_type
                if len(move_ids) == 1
                else (
                    any(move.move_type in ('in_invoice', 'out_invoice') for move in move_ids)
                    and 'some_invoice'
                    or False
                )
            )

    def reverse_moves(self):
        if not any(self.mapped('x_is_poland')):
            return super().reverse_moves()

        ctx = dict(self.env.context)

        if self.selected_correction_invoice:
            ctx['active_id'] = self.selected_correction_invoice.refund_invoice_id.id
            ctx['active_ids'] = [self.selected_correction_invoice.refund_invoice_id.id]

        rec = self.with_context(ctx)

        moves = (
            self.env['account.move'].browse(self.env.context['active_ids'])
            if self.env.context.get('active_model') == 'account.move'
            else rec.move_ids
        )

        default_values_list = []
        for move in moves:
            default_values_list.append(
                {
                    'ref': rec.reason,
                    'date': rec.date or move.date,
                    'invoice_date': move.is_invoice(include_receipts=True) and (rec.date or move.date) or False,
                    'journal_id': rec.journal_id and rec.journal_id.id or move.journal_id.id,
                    'invoice_payment_term_id': None,
                    'auto_post': True if rec.date > fields.Date.context_today(rec) else False,
                    'selected_correction_invoice': rec.selected_correction_invoice.id,
                    'invoice_user_id': move.invoice_user_id.id,
                    'partner_bank_id': move.partner_bank_id.id,
                }
            )

        if rec.refund_method == 'cancel':
            if any([vals.get('auto_post', False) for vals in default_values_list]):
                # noinspection PyProtectedMember
                new_moves = moves._reverse_moves(default_values_list)
            else:
                # noinspection PyProtectedMember
                new_moves = moves._reverse_moves(default_values_list, cancel=True)

        elif rec.refund_method == 'modify':
            # noinspection PyProtectedMember
            moves._reverse_moves(default_values_list, cancel=True)
            moves_vals_list = []
            for move in moves.with_context(include_business_fields=True):
                moves_vals_list.append(
                    move.copy_data({'invoice_payment_ref': move.name, 'date': rec.date or move.date})[0]
                )
            new_moves = self.env['account.move'].create(moves_vals_list)

        elif rec.refund_method == 'refund':
            # noinspection PyProtectedMember
            new_moves = moves.with_context(check_move_validity=False)._reverse_moves(default_values_list)

        else:
            return

        action = {'name': _('Reverse Moves'), 'type': 'ir.actions.act_window', 'res_model': 'account.move'}

        if len(new_moves) == 1:
            action.update({'view_mode': 'form', 'res_id': new_moves.id})

        else:
            action.update({'view_mode': 'tree,form', 'domain': [('id', 'in', new_moves.ids)]})

        return action
