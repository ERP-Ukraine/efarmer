import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()

        if self._context.get('x_skip_cash_valuation') and self.journal_id.x_cash_valuation_as_draft:
            return res

        for move_id in self.filtered(lambda _m_id: _m_id.journal_id.x_cash_valuation_method):
            _logger.info(f'Applying Cash valuation method for #{move_id.id}')

            if not move_id.statement_line_id:
                _logger.warning(f'Cash valuation method applied for move #{move_id.id} without statement line.')
                continue

            move_id.statement_line_id._x_check_date_allowed_for_valuation()
            move_id.statement_line_id._x_prepare_line_for_valuation()

            if move_id.journal_id.x_cash_valuation_method != 'fifo':
                continue

            if (
                zero_compare := move_id.statement_line_id.currency_id.compare_amounts(
                    move_id.statement_line_id.amount, 0
                )
            ) == -1:
                move_id.statement_line_id._x_consume_fifo_valuation_lines()
            elif zero_compare == 1:
                move_id.statement_line_id._x_adjust_fifo_valuation_lines()

        return res
