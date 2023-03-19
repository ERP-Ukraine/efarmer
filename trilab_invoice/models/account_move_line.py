from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    _sql_constraints = [('check_credit_debit', 'CHECK(True)', 'Wrong credit or debit value in accounting entry!')]

    corrected_line = fields.Boolean(default=False)

    # only for user input/visualization
    # x_price_unit_reverse = fields.Float(compute='x_compute_reverse', inverse='x_set_price_unit_reverse',
    #                                     store=False, readonly=False)
    x_quantity_reverse = fields.Float(
        compute='x_compute_reverse',  # inverse='x_set_quantity_reverse',
        digits='Product Unit of Measure',
        store=False,
        readonly=False,
    )
    x_price_subtotal_reverse = fields.Float(compute='x_compute_reverse', store=False, readonly=True)
    x_price_total_reverse = fields.Float(compute='x_compute_reverse', store=False, readonly=True)

    x_move_type = fields.Selection(related='move_id.move_type', store=False)

    @api.depends('quantity', 'price_unit', 'price_subtotal', 'price_total')
    def x_compute_reverse(self):
        for line in self:
            sign = -1  # if line.corrected_line else 1
            # line.x_price_unit_reverse = sign * line.price_unit
            line.x_quantity_reverse = sign * line.quantity
            line.x_price_subtotal_reverse = sign * line.price_subtotal
            line.x_price_total_reverse = sign * line.price_total
            # sign = -1 if line.corrected_line else 1
            # line.price_unit_inverse = sign * line.price_unit
            # line.price_subtotal_inverse = sign * line.price_subtotal
            # line.price_total_inverse = sign * line.price_total

    @api.onchange('x_quantity_reverse', 'x_price_subtotal_reverse', 'x_price_total_reverse')
    def x_set_reverse_values(self):
        for line in self:
            # line.price_unit = -line.price_unit_inverse
            line.quantity = -line.x_quantity_reverse
            line.price_subtotal = -line.x_price_subtotal_reverse
            line.price_total = -line.x_price_total_reverse
            # noinspection PyProtectedMember
            line._onchange_price_subtotal()
            # line.price_unit = -line.price_unit_inverse
            # line.price_subtotal = -line.price_subtotal_inverse
            # line.price_total = -line.price_total_inverse

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
