from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    order_ids = fields.Many2many('sale.order', readonly=1)
    order_line = fields.One2many('sale.order.line', compute='compute_order_line')
    invoice_lines = fields.Many2many('sale.order.line')
    advance_lines = fields.One2many('sale.advance.line', 'wizard_id')
    has_advances = fields.Boolean(compute='compute_has_advances', store=False)
    advance_payment_method_2 = fields.Selection(
        [('normal', 'Normal Invoice'), ('advance', 'Advance Invoice')],
        default='normal',
        required=1,
        string='Invoice Type',
    )
    x_journal_id = fields.Many2one('account.journal', string='Sale Journal')
    x_convert_to_pln = fields.Boolean(string='Convert To PLN')
    x_convert_rate = fields.Many2one('res.currency.rate', string='Convert Rate')
    x_orders_currency_id = fields.Many2one(
        'res.currency', string='Orders Currency', compute='_x_compute_orders_currency_id'
    )
    x_is_convertible = fields.Boolean(string='Is Convertible', compute='_x_compute_orders_currency_id')
    x_partner_bank_id = fields.Many2one('res.partner.bank', string='Account Number')
    x_allowed_partner_bank_ids = fields.Many2many(
        'res.partner.bank', compute='_x_compute_allowed_partner_bank_accounts'
    )

    def _x_get_is_poland(self):
        return self.env['account.move'].x_get_is_poland()

    @api.onchange('advance_payment_method_2')
    def _x_onchange_advance_payment_method_2(self):
        if self._x_get_is_poland():
            if self.advance_payment_method_2 == 'normal':
                self.advance_payment_method = 'delivered'
            else:
                self.advance_payment_method = 'percentage'

    @api.depends('order_ids')
    def compute_order_line(self):
        for wizard in self:
            wizard.order_line = [(6, 0, self.order_ids.mapped('order_line').ids)]

    @api.depends('order_ids')
    def compute_has_advances(self):
        for wizard in self:
            wizard.has_advances = any(line.is_downpayment for line in wizard.order_line)

    @api.depends('order_ids.currency_id')
    def _x_compute_orders_currency_id(self):
        pln = self.env.ref('base.PLN')
        for wizard in self:
            currency_ids = wizard.order_ids.mapped('currency_id')
            wizard.x_is_convertible = (
                all(currency == currency_ids[0] for currency in currency_ids)
                and all(
                    currency_id == pln for currency_id in wizard.order_ids.mapped('invoice_ids').mapped('currency_id')
                )
                and currency_ids[0] != pln
            )

            wizard.x_orders_currency_id = currency_ids[0] if wizard.x_is_convertible else False

    @api.onchange('x_convert_to_pln')
    def _x_onchange_convert_to_pln(self):
        if self.x_convert_to_pln:
            self.currency_id = self.env.ref('base.PLN')
        else:
            self.x_convert_rate = False

    @api.model
    def default_get(self, fields_list):
        output = super().default_get(fields_list)
        if not self._x_get_is_poland():
            return output

        orders = self.env['sale.order'].browse(self.env.context['active_ids'])
        output['order_ids'] = [(6, 0, orders.ids)]
        output['invoice_lines'] = [
            (6, 0, orders.order_line.filtered(lambda lne: lne.invoice_status == 'to invoice' or lne.display_type).ids)
        ]
        output['advance_payment_method'] = 'delivered'
        return output

    @api.onchange('x_allowed_partner_bank_ids')
    def _x_onchange_set_partner_bank_account(self):
        self.ensure_one()
        self.x_partner_bank_id = self.x_allowed_partner_bank_ids._origin[:1]

    @api.depends('order_ids.currency_id', 'order_ids.company_id', 'x_convert_to_pln')
    def _x_compute_allowed_partner_bank_accounts(self):
        pln = self.env.ref('base.PLN')
        for wizard in self:
            currency_id = pln if wizard.x_convert_to_pln else wizard.order_ids[:1].currency_id

            wizard.x_allowed_partner_bank_ids = self.env['res.partner.bank'].search(
                [
                    ('partner_id', '=', wizard.order_ids[:1].company_id.partner_id.id),
                    ('currency_id', '=', currency_id.id),
                ]
            )

    @api.onchange('advance_payment_method', 'invoice_lines')
    def onchange_advance_payment_method(self):
        if not self._x_get_is_poland():
            return super().onchange_advance_payment_method()

        if len(self._context.get('active_ids', [])) == 1:
            advance_lines = [(6, 0, [])]
            inv_lines = self.env['sale.order.line'].browse(self.order_line.ids)
            taxes = inv_lines.mapped('tax_id')
            for tax in taxes:
                lines = inv_lines.filtered(lambda lne: lne.tax_id.ids == [tax.id])
                currency_id = self.currency_id or self.env.company.currency_id
                subtotal = currency_id.round(sum(line.price_subtotal for line in lines))
                advance_lines.append(
                    (
                        0,
                        0,
                        {
                            'tax_id': tax.id,
                            'original_subtotal': subtotal,
                            'original_total': currency_id.round(subtotal * (1.0 + (tax.amount / 100.0))),
                            'currency_id': currency_id.id,
                        },
                    )
                )
            self.advance_lines = advance_lines

    def _prepare_invoice_values(self, order, name, amount, so_line):
        # noinspection PyProtectedMember
        invoice_vals = super()._prepare_invoice_values(order, name, amount, so_line)
        if not self._x_get_is_poland():
            return invoice_vals

        if not invoice_vals.get('x_invoice_sale_date'):
            invoice_vals['x_invoice_sale_date'] = fields.Date.context_today(order)

        invoice_vals.update(
            {
                # 'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
                'is_downpayment': True if (self.env.context['invoice_type'] == 'percentage') else False,
                'partner_bank_id': self.x_partner_bank_id.id,
            }
        )

        if self.x_convert_to_pln:
            invoice_vals['currency_id'] = self.env.ref('base.PLN').id

        so_lines = self.env.context.get('so_advance_lines', [])

        if so_lines:
            invoice_vals['invoice_line_ids'] = [
                (
                    0,
                    0,
                    {
                        'name': self.product_id.name,
                        'price_unit': _line.price_unit
                        if not self.x_convert_to_pln
                        else _line.price_unit * self.x_convert_rate.inverse_company_rate,
                        'quantity': 1.0,
                        'product_id': self.product_id.id,
                        'product_uom_id': _line.product_uom.id,
                        'tax_ids': [(6, 0, _line.tax_id.ids)],
                        'sale_line_ids': [(6, 0, [_line.id])],
                        'analytic_tag_ids': [(6, 0, _line.analytic_tag_ids.ids)],
                        'analytic_account_id': order.analytic_account_id.id or False,
                    },
                )
                for _line in so_lines
            ]

        return invoice_vals

    def _create_invoice(self, order, so_line, amount):
        if not self._x_get_is_poland():
            # noinspection PyProtectedMember
            return super()._create_invoice(order, so_line, amount)

        amount, name = self._get_advance_details(order)
        invoice_vals = self._prepare_invoice_values(order, name, amount, so_line)
        if self.x_convert_rate:
            invoice_vals['narration'] = _(
                'Rate %s with effective date: %s', self.x_convert_rate.inverse_company_rate, self.x_convert_rate.name
            )
        if order.fiscal_position_id:
            invoice_vals['fiscal_position_id'] = order.fiscal_position_id.id

        # check if we should update currency rate
        ctx = {}
        if (
            order.company_id.x_enable_invoice_rate_change
            and order.pricelist_id.currency_id != order.company_id.currency_id
        ):
            rate = self.env['res.currency']._get_conversion_rate(
                order.pricelist_id.currency_id,
                order.company_id.currency_id,
                order.company_id,
                invoice_vals.get('x_invoice_sale_date')
                or invoice_vals.get('invoice_date')
                or invoice_vals.get('date')
                or fields.Date.context_today(self),
            )
            if not order.company_id.currency_id.is_zero(rate):
                ctx['x_trilab_force_currency_rate'] = rate

        invoice = self.env['account.move'].sudo().with_context(**ctx).create(invoice_vals).with_user(self.env.uid)

        order.check_advance_invoice_values()
        invoice.message_post_with_view(
            'mail.message_origin_link',
            values={'self': invoice, 'origin': order},
            subtype_id=self.env.ref('mail.mt_note').id,
        )
        return invoice

    def _prepare_deposit_product(self):
        output = super()._prepare_deposit_product()
        if not self._x_get_is_poland():
            return output

        output['name'] = _('Advance payment')
        return output

    def _prepare_so_line(self, order, analytic_tag_ids, tax_ids, amount):
        so_values = super()._prepare_so_line(order, analytic_tag_ids, tax_ids, amount)

        if self._x_get_is_poland():
            so_values['name'] = _('Advance payment [%s]', self.env['account.tax'].browse(tax_ids[0]).description)

        return so_values

    def create_invoices(self):
        if not self._x_get_is_poland():
            return super().create_invoices()

        ctx = dict(self.env.context)
        ctx.update(
            {
                'selected_invoice_lines': self.invoice_lines.ids,
                'invoice_type': self.advance_payment_method,
                'x_journal_id': self.x_journal_id.id,
                'x_convert_rate': self.x_convert_rate.id,
                'x_partner_bank_id': self.x_partner_bank_id.id,
            }
        )

        self = self.with_context(ctx)
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method_2 == 'normal':
            if not self.invoice_lines.filtered(
                lambda invoice_line: not invoice_line.is_downpayment and not invoice_line.display_type
            ):
                raise ValidationError(_('No delivered lines to invoice'))

        if self.advance_payment_method == 'delivered':
            sale_orders._create_invoices(final=self.deduct_down_payments)

        else:
            if not self.product_id:
                vals = self._prepare_deposit_product()
                if 'taxes_id' in vals:
                    vals.pop('taxes_id')

                # noinspection PyAttributeOutsideInit
                self.product_id = self.env['product.product'].create(vals)
                self.env['ir.config_parameter'].sudo().set_param(
                    'sale.default_deposit_product_id', str(self.product_id.id)
                )

            sale_line_obj = self.env['sale.order.line']
            for order in sale_orders:
                if self.product_id.invoice_policy != 'order':
                    raise UserError(
                        _(
                            'The product used to invoice a down payment should have an invoice policy set to '
                            '"Ordered quantities". Please update your deposit product to be able to create a '
                            'deposit invoice.'
                        )
                    )

                if self.product_id.type != 'service':
                    raise UserError(
                        _(
                            "The product used to invoice a down payment should be of type 'Service'. "
                            "lease use another product or update this product."
                        )
                    )

                so_lines = self.env['sale.order.line']
                so_lines_values = []
                advance_lines = self.advance_lines.filtered(lambda al: al.value > 0)

                if not advance_lines:
                    raise UserError(_('Invalid advance invoice lines'))

                for adv_line in advance_lines:
                    amount = adv_line.value
                    analytic_tag_ids = []
                    for line in order.order_line:
                        analytic_tag_ids = [(4, analytic_tag.id, None) for analytic_tag in line.analytic_tag_ids]
                    so_line_values = self._prepare_so_line(order, analytic_tag_ids, adv_line.tax_id.ids, amount)
                    so_lines_values.append(so_line_values)
                    so_lines += sale_line_obj.create(so_line_values)

                # noinspection PyProtectedMember
                self.with_context(so_advance_lines=so_lines)._create_invoice(
                    order, so_lines[:1], sum(so_lines.mapped('price_unit'))
                )

        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()

        return {'type': 'ir.actions.act_window_close'}


class SaleAdvanceLine(models.TransientModel):
    _name = 'sale.advance.line'
    _description = 'Sale Advance Line'

    @api.constrains('value', 'percent')
    def constrains_values(self):
        for line in self:
            if line.wizard_id.advance_payment_method == 'delivered':
                continue

            if line.percent < 0:
                raise UserError(_('Percent Value must be positive'))

            if line.percent > 100:
                raise UserError(_('Percent Value cannot be greater than 100%'))

            total = line.original_total if line.tax_id.price_include else line.original_subtotal

            if line.percent:
                line.write(dict(value=total * (line.percent / 100), percent=0))

            if line.value < 0:
                raise UserError(_('Advance line value must be positive'))

            # rounding issue #4245
            if line.value - total > 0.05:
                raise UserError(_('Advance line value is bigger than order value'))

    @api.onchange('value')
    def onchange_value(self):
        if 'value' not in self.env.context:
            return
        value_total = self.value * (1.0 + (self.tax_id.amount / 100.0))
        percent = (self.value / self.original_subtotal) * 100.0
        self.write(dict(value_total=value_total, percent=percent))

    @api.onchange('value_total')
    def onchange_value_total(self):
        if 'value_total' not in self.env.context:
            return
        value = self.value_total / (1 + (self.tax_id.amount / 100.0))
        percent = (value / self.original_subtotal) * 100.0
        self.write(dict(value=value, percent=percent))

    @api.onchange('percent')
    def onchange_percent(self):
        if 'percent' not in self.env.context:
            return

        value = self.currency_id.round(self.original_subtotal * (self.percent / 100.0))
        value_total = self.currency_id.round(value * (1.0 + (self.tax_id.amount / 100.0)))
        self.write(dict(value=value, value_total=value_total))

    wizard_id = fields.Many2one('sale.advance.payment.inv', required=1)
    tax_id = fields.Many2one('account.tax', required=1)
    original_subtotal = fields.Monetary()
    original_total = fields.Monetary()
    value = fields.Monetary(required=0, string='Value [NET]')
    value_total = fields.Monetary(required=0, string='Value [GROSS]')
    percent = fields.Float(required=0, string='Value Percent')
    currency_id = fields.Many2one('res.currency')
