from odoo import api, fields, models
from odoo.tools import float_is_zero


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_is_corrected_line = fields.Boolean(default=False)

    # only for user input/visualization
    x_quantity = fields.Float(compute='_x_compute_reverse', digits='Product Unit of Measure', readonly=False)
    x_price_subtotal = fields.Float(compute='_x_compute_reverse', store=False, readonly=True)
    x_price_total = fields.Float(compute='_x_compute_reverse', store=False, readonly=True)
    x_force_print = fields.Boolean('Force Print')

    @api.depends_context('x_show_as_before')
    @api.depends('quantity', 'price_unit', 'price_subtotal', 'price_total')
    def _x_compute_reverse(self):
        for line_id in self:
            sign = -1

            if self._context.get('x_show_as_before'):
                sign *= -1

            line_id.x_quantity = sign * line_id.quantity
            line_id.x_price_subtotal = sign * line_id.price_subtotal
            line_id.x_price_total = sign * line_id.price_total

    @api.onchange('x_quantity', 'x_price_subtotal', 'x_price_total')
    def x_set_reverse_values(self):
        for line_id in self:
            line_id.quantity = -line_id.x_quantity
            line_id.price_subtotal = -line_id.x_price_subtotal
            line_id.price_total = -line_id.x_price_total

    def _get_rate_date(self):
        self.ensure_one()

        if self.move_id.x_use_ti and self.move_id.x_invoice_sale_date:
            return self.move_id.x_invoice_sale_date

        return super()._get_rate_date()

    @api.depends('currency_id', 'company_id', 'move_id.invoice_currency_rate', 'move_id.date')
    def _compute_currency_rate(self):
        update_line_ids = self.filtered(lambda l_id: l_id.move_id.x_use_ti)

        for line_id in update_line_ids:
            if line_id.move_id.is_invoice(include_receipts=True):
                line_id.currency_rate = line_id.move_id.invoice_currency_rate or 1.0
            elif line_id.currency_id:
                line_id.currency_rate = self.env['res.currency']._get_conversion_rate(
                    from_currency=line_id.company_currency_id,
                    to_currency=line_id.currency_id,
                    company=line_id.company_id,
                    date=line_id._get_rate_date(),
                )
            else:
                line_id.currency_rate = 1.0

        super(AccountMoveLine, self - update_line_ids)._compute_currency_rate()

    def _x_stock_account_get_anglo_saxon_price_unit(self):
        # modified _stock_account_get_anglo_saxon_price_unit from sale_stock

        so_line_id = self.sale_line_ids and self.sale_line_ids[-1] or False
        price_unit = None
        if so_line_id:
            qty_to_invoice = self.product_uom_id._compute_quantity(self.quantity, self.product_id.uom_id)
            account_move_ids = so_line_id.invoice_lines.move_id.filtered(
                lambda m_id: m_id.state == 'posted' and not m_id.reversed_entry_id
            )

            posted_cogs_ids = self.env['account.move.line'].search(
                [
                    ('move_id', 'in', account_move_ids.ids),
                    ('display_type', '=', 'cogs'),
                    ('product_id', '=', self.product_id.id),
                    ('balance', '>', 0),
                ]
            )

            posted_cogs_ids = posted_cogs_ids.filtered(lambda l_id: so_line_id in l_id.cogs_origin_id.sale_line_ids)

            qty_invoiced = 0

            for line_id in posted_cogs_ids:
                qty_invoiced += line_id.product_uom_id._compute_quantity(line_id.quantity, line_id.product_id.uom_id)

            value_invoiced = sum(posted_cogs_ids.mapped('balance'))
            reversal_move_ids = self.env['account.move']._search(
                [('reversed_entry_id', 'in', posted_cogs_ids.move_id.ids)]
            )

            reversal_cogs_ids = self.env['account.move.line'].search(
                [
                    ('move_id', 'in', reversal_move_ids),
                    ('display_type', '=', 'cogs'),
                    ('product_id', '=', self.product_id.id),
                    ('balance', '>', 0),
                ]
            )

            reversal_cogs_ids = reversal_cogs_ids.filtered(lambda l_id: l_id.cogs_origin_id.x_is_corrected_line)

            for line_id in reversal_cogs_ids:
                qty_invoiced -= line_id.product_uom_id._compute_quantity(line_id.x_quantity, line_id.product_id.uom_id)
                value_invoiced -= abs(line_id.balance)

            product_id = self.product_id.with_company(self.company_id).with_context(value_invoiced=value_invoiced)
            # noinspection PyUnresolvedReferences
            average_price_unit = product_id._compute_average_price(qty_invoiced, qty_to_invoice, so_line_id.move_ids)
            price_unit = self.product_id.uom_id.with_company(self.company_id)._compute_price(
                average_price_unit, self.product_uom_id
            )

        return price_unit

    def _stock_account_get_anglo_saxon_price_unit(self):
        # from stock_account
        # noinspection PyUnresolvedReferences
        price_unit = super()._stock_account_get_anglo_saxon_price_unit()

        # Fix of Odoo bug, applied to Polish companies' Credit Notes.
        # The first level of the parent method has been used here as a fix (stock_account/models/account_move.py)
        if not self.move_id.x_use_ti or not self.sale_line_ids:
            return price_unit

        if not self.product_id:
            return self.price_unit

        account_move_id = self.move_id.reversed_entry_id
        has_posted_refunds = False

        # find original account.move for SO with already posted invoice and refund
        if not account_move_id and (
                (
                        so_posted_move_ids := (self.sale_line_ids.invoice_lines - self).move_id.filtered(
                            lambda m_id: m_id.state == 'posted'
                        )
                )
                and (has_posted_refunds := so_posted_move_ids.filtered(lambda m_id: m_id.move_type == 'out_refund'))
                and (invoice_move_ids := so_posted_move_ids.filtered(lambda m_id: m_id.move_type == 'out_invoice'))
        ):
            account_move_id = fields.first(invoice_move_ids)

        while account_move_id.reversed_entry_id:
            account_move_id = account_move_id.reversed_entry_id

        cogs_original_line_id = self.env['account.move.line']

        if self.move_type != 'out_refund':
            if not has_posted_refunds:
                return price_unit

            # fix for computing price unit for SaleOrder with multiple invoices with refunds
            new_price_unit = self._x_stock_account_get_anglo_saxon_price_unit()

            return new_price_unit if new_price_unit is not None else price_unit

        lines_field_name = 'x_corrected_invoice_line_ids' if self.x_is_corrected_line else 'x_original_invoice_line_ids'

        for current_line_id, original_line_id in zip(
                self.move_id[lines_field_name], account_move_id.invoice_line_ids, strict=False
        ):
            if current_line_id == self:
                cogs_original_line_id = original_line_id.move_id.line_ids.filtered(
                    lambda _l_id: (
                            _l_id.cogs_origin_id == original_line_id
                            and _l_id.currency_id.compare_amounts(_l_id.price_unit, 0.0) >= 0
                    )
                )
                break

        if cogs_original_line_id:
            return self.product_id.uom_id.with_company(self.company_id)._compute_price(
                price=abs(cogs_original_line_id.balance / cogs_original_line_id.quantity), to_unit=self.product_uom_id
            )
        return price_unit

    def _eligible_for_cogs(self):
        # noinspection PyUnresolvedReferences
        res = super()._eligible_for_cogs()

        if (
                not res
                or self.move_type != 'out_refund'
                or not self.move_id.x_use_ti
                or not self._context.get('x_ti_additional_checks_eligible_for_cogs')
        ):
            return res

        # for matching the invoice line from an opposite site (x_is_corrected_line)
        # sum quantity of this line and self.quantity and check if it is zero
        opposite_line_id = self.env['account.move.line']
        for corrected_line_id, original_line_id in zip(
                self.move_id.x_corrected_invoice_line_ids, self.move_id.x_original_invoice_line_ids
        ):
            if self.x_is_corrected_line and corrected_line_id == self:
                opposite_line_id = original_line_id
                break
            elif not self.x_is_corrected_line and original_line_id == self:
                opposite_line_id = corrected_line_id
                break

        return not float_is_zero(
            opposite_line_id.quantity + self.quantity,
            precision_digits=self.env['decimal.precision'].precision_get('Product Unit of Measure'),
        )

    def x_can_print(self):
        self.ensure_one()

        if not self.move_id.x_use_ti or not self.company_id.x_hide_zero_price_aml:
            return True

        return (
                self.x_force_print
                or self.display_type in ('line_section', 'line_note')
                or not self.currency_id.is_zero(self.price_unit)
        )

    def x_get_net_price_unit(self, before_discount=False):
        self.ensure_one()

        # handle precision, even if UOM is not set
        if self.product_uom_id:
            rounding = self.product_uom_id.rounding
        else:
            rounding = 1 / 10 ** self.env['decimal.precision'].precision_get('Product Unit of Measure')

        if float_is_zero(self.quantity, precision_rounding=rounding):
            return 0.0

        line_record = self.move_id._prepare_product_base_line_for_taxes_computation(self)

        # workaround on rounding in taxes.compute_all, later it is multiplied
        line_record['quantity'] /= rounding

        if before_discount:
            line_record['discount'] = 0.0

        self.env['account.tax']._add_tax_details_in_base_line(line_record, self.company_id)

        return line_record['tax_details']['raw_total_excluded_currency'] / self.quantity * rounding

    def _apply_price_difference(self):
        # from purchase_stock
        # noinspection PyUnresolvedReferences
        return super(
            AccountMoveLine,
            self.filtered(lambda line_id: not (line_id.move_id.x_use_ti and line_id.move_id.x_is_refund())),
        )._apply_price_difference()
