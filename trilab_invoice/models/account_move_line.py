from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    _sql_constraints = [('check_credit_debit', 'CHECK(True)', 'Wrong credit or debit value in accounting entry!')]

    corrected_line = fields.Boolean(default=False)

    x_quantity_reverse = fields.Float(
        compute='x_compute_reverse',  # inverse='x_set_quantity_reverse',
        digits='Product Unit of Measure',
        store=False,
        readonly=False,
    )
    x_price_subtotal_reverse = fields.Float(compute='x_compute_reverse', store=False, readonly=True)
    x_price_total_reverse = fields.Float(compute='x_compute_reverse', store=False, readonly=True)

    x_move_type = fields.Selection(related='move_id.move_type', store=False)
    x_force_print = fields.Boolean('Force Print')

    @api.depends_context('x_show_as_before')
    @api.depends('quantity', 'price_unit', 'price_subtotal', 'price_total')
    def x_compute_reverse(self):
        for line in self:
            sign = line.move_id.x_invoice_sign

            if self._context.get('x_show_as_before'):
                sign *= -1

            line.x_quantity_reverse = sign * line.quantity
            line.x_price_subtotal_reverse = sign * line.price_subtotal
            line.x_price_total_reverse = sign * line.price_total

    @api.onchange('x_quantity_reverse', 'x_price_subtotal_reverse', 'x_price_total_reverse')
    def x_set_reverse_values(self):
        for line in self.filtered(lambda lne: not lne.x_move_type.endswith('_invoice')):
            # line.price_unit = -line.price_unit_inverse
            line.quantity = -line.x_quantity_reverse
            line.price_subtotal = -line.x_price_subtotal_reverse
            line.price_total = -line.x_price_total_reverse

    def _get_computed_price_unit(self):
        self.ensure_one()

        if self.move_id.x_get_is_poland() and self.corrected_line:
            return self.price_unit

        # noinspection PyProtectedMember
        return super()._get_computed_price_unit()

    def run_onchanges(self):
        self._onchange_mark_recompute_taxes()
        self._onchange_balance()
        self._onchange_debit()
        self._onchange_credit()
        self._onchange_amount_currency()
        self._onchange_price_subtotal()
        self._onchange_currency()

    @api.model
    def _get_fields_onchange_balance_model(
        self, quantity, discount, amount_currency, move_type, currency, taxes, price_subtotal, force_computation=False
    ):
        if self.corrected_line:
            return {}  # do not change anything

        # noinspection PyProtectedMember
        return super()._get_fields_onchange_balance_model(
            quantity, discount, amount_currency, move_type, currency, taxes, price_subtotal, force_computation
        )

    def x_get_net_price_unit(self):
        return self._get_price_total_and_subtotal(quantity=1)['price_subtotal']

    @api.onchange('quantity', 'discount', 'price_unit', 'tax_ids')
    def _onchange_price_subtotal(self):
        return super(
            AccountMoveLine, self.move_id._x_update_context_with_currency_rate(self)
        )._onchange_price_subtotal()

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        return super(
            AccountMoveLine, self.move_id._x_update_context_with_currency_rate(self)
        )._onchange_amount_currency()

    def _stock_account_get_anglo_saxon_price_unit(self):
        # from stock_account
        # noinspection PyUnresolvedReferences
        price_unit = super()._stock_account_get_anglo_saxon_price_unit()

        # Fix of Odoo bug, applied to Polish companies' Credit Notes.
        # The first level of parent method has been used here as a fix (stock_account/models/account_move.py)
        if not self.move_id.x_get_is_poland() or not self.sale_line_ids:
            return price_unit

        if not self.product_id:
            return self.price_unit

        account_move_id = self.move_id.reversed_entry_id

        # find original account.move for SO with already posted invoice and refund
        if (
            not account_move_id
            and (
                so_posted_move_ids := (self.sale_line_ids.invoice_lines - self).move_id.filtered(
                    lambda _m: _m.state == 'posted'
                )
            )
            and (invoice_move_ids := so_posted_move_ids.filtered(lambda _m: _m.move_type == 'out_invoice'))
            and so_posted_move_ids.filtered(lambda _m: _m.move_type == 'out_refund')
        ):
            account_move_id = fields.first(invoice_move_ids)

        # noinspection PyUnresolvedReferences
        original_line = fields.first(
            account_move_id.line_ids.filtered(
                lambda _l: _l.is_anglo_saxon_line
                and _l.product_id == self.product_id
                and _l.product_uom_id == self.product_uom_id
                and _l.currency_id == self.currency_id
                and float_compare(
                    _l.price_unit, 0.0, precision_digits=self.env['decimal.precision'].precision_get('Product Price')
                )
                >= 0
            )
        )

        return original_line.price_unit if original_line else price_unit

    def _eligible_for_cogs(self):
        # noinspection PyUnresolvedReferences
        res = super()._eligible_for_cogs()

        if (
            not res
            or self.x_move_type != 'out_refund'
            or not self.move_id.x_get_is_poland()
            or not self._context.get('x_ti_additional_checks_eligible_for_cogs')
        ):
            return res

        product_line_ids = self.move_id.invoice_line_ids.filtered(
            lambda _l_id: _l_id.product_id == self.product_id and _l_id.product_uom_id == self.product_uom_id
        ).sorted('id')

        opposite_site_line_ids = product_line_ids.filtered(
            lambda _l_id: _l_id.corrected_line is (not self.corrected_line)
        )

        # take appropriate line from the opposite site, based on position in sorted recordset
        try:
            opposite_site_line_quantity = opposite_site_line_ids[
                list(product_line_ids - opposite_site_line_ids).index(self)
            ].quantity
        except IndexError:
            opposite_site_line_quantity = 0

        # for matching invoice line from another site (corrected_line)
        # sum quantity of this line and self.quantity and check if it is zero
        return not float_is_zero(
            opposite_site_line_quantity + self.quantity,
            precision_digits=self.env['decimal.precision'].precision_get('Product Unit of Measure'),
        )

    def x_can_print(self):
        self.ensure_one()

        if not self.move_id.x_get_is_poland() or not self.company_id.x_hide_zero_price_aml:
            return True

        return (
            self.x_force_print
            or self.display_type in ('line_section', 'line_note')
            or not self.currency_id.is_zero(self.price_unit)
        )
