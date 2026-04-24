import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr

_logger = logging.getLogger(__name__)


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    x_is_valuation_line = fields.Boolean('Valuation Line')
    x_is_valuation_used = fields.Boolean('Valuation Used', readonly=True)
    x_valuation_remaining_amount = fields.Monetary('Valuation Remaining Amount')
    x_can_edit_valuation = fields.Boolean(
        compute='_x_compute_can_edit_valuation',
        string='Can Edit Valuation',
    )

    def _x_compute_can_edit_valuation(self):
        self.x_can_edit_valuation = self.env.user.has_group('account.group_account_manager')

    def _x_check_date_allowed_for_valuation(self):
        self.ensure_one()

        if self.search_count(
            [
                ('journal_id', '=', self.journal_id.id),
                ('date', '>', self.date),
                ('x_is_valuation_used', '=', True),
            ],
        ):
            raise ValidationError(
                _('Cannot add record with a date, that is earlier than statement line that contains a valuation.')
            )

    def _x_prepare_line_for_valuation(self):
        self.ensure_one()

        self.write(
            {
                'x_is_valuation_used': False,
                'x_is_valuation_line': True,
                'x_valuation_remaining_amount': (
                    self.amount if self.currency_id.compare_amounts(self.amount, 0) == 1 else None
                ),
            }
        )

    def _x_valuation_synchronize_to_moves(self, stmt_line_id_consumed_map: dict):
        self.ensure_one()

        self = self.with_context(skip_account_move_synchronization=True)

        amount_company_currency = 0
        amount_currency = 0
        message_stmt_line_id_consumed_map = {}
        precision_digits = max(4, self.company_currency_id.decimal_places)
        for stmt_line_id, amount_consumed in stmt_line_id_consumed_map.items():
            if stmt_line_id:
                # ensure balance is not 0 to avoid ZeroDivisionError
                aml_id = fields.first(
                    stmt_line_id.move_id.line_ids.filtered(lambda _aml_id: _aml_id.currency_id and _aml_id.balance)
                )

                if not aml_id:
                    _logger.debug(f'No valid account move line found for: {stmt_line_id}')
                    continue

                message_stmt_line_id_consumed_map[stmt_line_id] = {
                    'amount_consumed': stmt_line_id.currency_id.format(amount_consumed),
                    'currency_rate': float_repr(
                        1 / (currency_rate := aml_id.amount_currency / abs(aml_id.balance)),
                        precision_digits=precision_digits,
                    ),
                    'amount_company_currency': stmt_line_id.company_currency_id.format(
                        _amount_company_currency := amount_consumed / currency_rate
                    ),
                    'date': stmt_line_id.date,
                }
            else:
                message_stmt_line_id_consumed_map[stmt_line_id] = {
                    'amount_consumed': self.currency_id.format(amount_consumed),
                    'currency_rate': float_repr(
                        1
                        / (
                            currency_rate := self.currency_id._get_conversion_rate(
                                self.company_currency_id,
                                self.currency_id,
                                date=self.date,
                            )
                        ),
                        precision_digits=precision_digits,
                    ),
                    'amount_company_currency': self.company_currency_id.format(
                        _amount_company_currency := amount_consumed / currency_rate
                    ),
                    'date': self.date,
                }

            amount_company_currency += _amount_company_currency
            amount_currency += amount_consumed

        amount_company_currency = self.company_id.currency_id.round(amount_company_currency)

        liquidity_line_ids, suspense_line_ids, other_line_ids = self._seek_for_lines()

        line_ids_commands = [
            fields.Command.update(
                _line_id.id, {'debit': 0, 'credit': amount_company_currency, 'amount_currency': -amount_currency}
            )
            for _line_id in liquidity_line_ids
        ]

        if suspense_line_ids:
            line_ids_commands += [
                fields.Command.update(
                    _line_id.id, {'debit': amount_company_currency, 'credit': 0, 'amount_currency': amount_currency}
                )
                for _line_id in suspense_line_ids
            ]

        if other_line_ids:
            if not suspense_line_ids:
                line_ids_commands += [
                    fields.Command.update(
                        _line_id.id,
                        {'debit': amount_company_currency, 'credit': 0, 'amount_currency': amount_currency},
                    )
                    for _line_id in other_line_ids
                ]
            else:
                line_ids_commands += [fields.Command.delete(_line_id.id) for _line_id in other_line_ids]

        self.move_id.with_context(skip_readonly_check=True).line_ids = line_ids_commands

        self.move_id.message_post_with_source(
            'trilab_cash_fifo.message_valuation_consumed',
            render_values={
                'self': self,
                'message_stmt_line_id_consumed_map': message_stmt_line_id_consumed_map,
            },
            subtype_xmlid='mail.mt_note',
        )

    def _x_consume_fifo_valuation_lines(self):
        self.ensure_one()

        _logger.debug(f'Consuming valuation lines for: {self}...')

        stmt_line_ids = self.search(
            [
                ('journal_id', '=', self.journal_id.id),
                ('date', '<=', self.date),
                ('x_is_valuation_line', '=', True),
                ('x_valuation_remaining_amount', '>', 0),
            ],
            order='date',
        )

        amount_to_consume = -self.amount
        consumed_stmt_line_ids = self.env['account.bank.statement.line']
        stmt_line_id_consumed_map = {}
        for stmt_line_id in stmt_line_ids:
            current_line_consumed_amount = min(stmt_line_id.x_valuation_remaining_amount, amount_to_consume)
            stmt_line_id_consumed_map[stmt_line_id] = current_line_consumed_amount

            amount_to_consume -= current_line_consumed_amount
            stmt_line_id.write(
                {
                    'x_is_valuation_used': True,
                    'x_valuation_remaining_amount': (
                        stmt_line_id.x_valuation_remaining_amount - current_line_consumed_amount
                    ),
                }
            )
            consumed_stmt_line_ids += stmt_line_id

            if self.currency_id.compare_amounts(amount_to_consume, 0) != 1:
                break

        if self.currency_id.compare_amounts(amount_to_consume, 0) == 1:
            _logger.debug(f'Amount to consume leftovers {amount_to_consume}')
            stmt_line_id_consumed_map[self.env['account.bank.statement.line']] = amount_to_consume

        _logger.debug(f'Consumed valuation lines: {consumed_stmt_line_ids}')
        self._x_valuation_synchronize_to_moves(stmt_line_id_consumed_map)

    def _x_adjust_fifo_valuation_lines(self):
        self.ensure_one()

        if (
            self.currency_id.compare_amounts(self.amount, 0) != 1
            or self.currency_id.compare_amounts(self.amount - self.running_balance, 0) != 1
        ):
            _logger.debug(f'Skipping adjusting valuation lines for: {self}...')
            return

        _logger.info(f'Adjusting valuation lines for: {self}...')

        self.write(
            {
                'x_is_valuation_used': True,
                'x_valuation_remaining_amount': self.running_balance
                if self.currency_id.compare_amounts(self.running_balance, 0) >= 0
                else 0,
            }
        )

    def _x_pre_write_valuation_checks(self, vals):
        self.ensure_one()

        if 'date' in vals:
            raise UserError(_('You cannot change the date of a valuation statement line.'))

        if 'amount' in vals and self.currency_id.compare_amounts(vals['amount'], self.amount) != 0:
            if self.x_is_valuation_used:
                raise UserError(_('You cannot change the amount of a statement line that has used valuation line.'))
            if self.currency_id.compare_amounts(vals['amount'] * self.amount, 0) == -1:
                raise UserError(_('You cannot change the amount to a value with different sign.'))
            if self.currency_id.compare_amounts(vals['amount'], 0) == -1:
                raise UserError(_('You cannot change the amount for negative lines.'))
            vals['x_valuation_remaining_amount'] = vals['amount']

    @api.model_create_multi
    def create(self, vals_list):
        # skip cash valuation for automatic post
        stmt_line_ids = super(AccountBankStatementLine, self.with_context(x_skip_cash_valuation=True)).create(vals_list)

        for stmt_line_id in stmt_line_ids.filtered(
            lambda stmt_id: stmt_id.journal_id.x_cash_valuation_method and stmt_id.journal_id.x_cash_valuation_as_draft
        ):
            # revert draft state for statement line
            stmt_line_id.move_id.button_draft()
            stmt_line_id.move_id.checked = False

        return stmt_line_ids

    def write(self, vals):
        for stmt_line_id in self.filtered('x_is_valuation_line'):
            stmt_line_id._x_pre_write_valuation_checks(vals)
        return super().write(vals)

    def _pre_unlink_valuation_checks(self):
        if self.filtered(
            lambda _stmt_line_id: _stmt_line_id.x_is_valuation_line
            and (
                _stmt_line_id.x_is_valuation_used
                or _stmt_line_id.currency_id.compare_amounts(_stmt_line_id.amount, 0) == -1
            )
        ):
            raise UserError(_('You cannot delete valuation lines that have been used or have negative amount.'))

    def unlink(self):
        self._pre_unlink_valuation_checks()
        return super().unlink()

    def x_post_move(self):
        self.ensure_one()

        self.move_id.checked = True
        self.move_id.action_post()

    def x_action_post_move(self):
        for line_id in self:
            line_id.x_post_move()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _('Posting Moves'),
                'message': _('Posted %s moves.', len(self)),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
