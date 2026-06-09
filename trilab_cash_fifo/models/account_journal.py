from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ALLOWED_JOURNAL_TYPES = {'cash', 'bank'}


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    x_cash_valuation_method = fields.Selection([('fifo', 'FIFO')], string='Cash Valuation Method')
    x_cash_valuation_as_draft = fields.Boolean(
        string='Cash Valuations as Draft', help='Create journal entries for cash valuations in the Draft state.'
    )
    x_cash_valuation_visible = fields.Boolean(compute='_x_cash_valuation_visible')

    @api.depends('currency_id', 'company_id.currency_id', 'type')
    def _x_cash_valuation_visible(self):
        for journal_id in self:
            journal_id.x_cash_valuation_visible = (
                journal_id.currency_id
                and journal_id.currency_id != journal_id.company_id.currency_id
                and journal_id.type in ALLOWED_JOURNAL_TYPES
            )

    @api.constrains('x_cash_valuation_method', 'type')
    def _x_check_cash_valuation_method(self):
        if self.filtered(
            lambda j_id: j_id.x_cash_valuation_method
            and (j_id.type not in ALLOWED_JOURNAL_TYPES or j_id.currency_id == j_id.company_id.currency_id)
        ):
            raise ValidationError(
                _(
                    'Cash Valuation Method can only be set for Cash and Bank journals'
                    ' in currencies different than Company Currency.'
                )
            )
