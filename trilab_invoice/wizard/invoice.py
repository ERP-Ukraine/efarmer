from collections import defaultdict

from markupsafe import Markup

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import UserError


class InvoiceWizard(models.TransientModel):
    _name = 'trilab.invoice.wizard'
    _description = 'Invoice Wizard'

    invoice_type = fields.Selection(
        [('normal', 'Normal Invoice'), ('advance', 'Advance Invoice')],
        default='normal',
        required=True,
        string='Invoice Type',
    )

    sale_order_ids = fields.Many2many('sale.order', default=lambda self: self.env.context.get('active_ids'))
    sale_order_count = fields.Integer(string='Order Count', compute='_compute_dynamic_fields')

    company_id = fields.Many2one(comodel_name='res.company', compute='_compute_currency_fields', store=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Company Currency')

    currency_id = fields.Many2one(
        comodel_name='res.currency', string='Currency', compute='_compute_currency_fields', store=True
    )
    is_convertible = fields.Boolean(string='Is Convertible', compute='_compute_currency_fields', store=True)
    convert_to_local = fields.Boolean(string='Convert To Local Currency')
    convert_rate_id = fields.Many2one('res.currency.rate', string='Convert Rate')

    journal_id = fields.Many2one('account.journal', string='Sale Journal', domain="[('type', '=', 'sale')]")

    partner_bank_id = fields.Many2one('res.partner.bank', string='Account Number')
    allowed_partner_bank_ids = fields.Many2many('res.partner.bank', compute='_compute_allowed_partner_bank_accounts')

    has_down_payments = fields.Boolean(string='Has down payments', compute='_compute_dynamic_fields')

    amount_invoiced = fields.Monetary(
        string='Already invoiced',
        compute='_compute_dynamic_fields',
        help='Only confirmed down payments are considered.',
    )
    amount_to_invoice = fields.Monetary(
        string='Amount to invoice',
        compute='_compute_dynamic_fields',
        help='The amount to invoice = Sale Order Total - Confirmed Down Payments.',
    )

    invoice_line_ids = fields.Many2many(
        'sale.order.line', compute='_compute_invoice_line_ids', inverse='_inverse_invoice_line_ids', readonly=True
    )

    advance_line_ids = fields.One2many(
        'trilab.invoice.wizard.line',
        'wizard_id',
        compute='_compute_advance_line_ids',
        inverse='_inverse_advance_line_ids',
        store=True,
        string='Advance Lines',
    )

    display_draft_invoice_warning = fields.Boolean(compute='_compute_display_draft_invoice_warning')
    display_invoice_amount_warning = fields.Boolean(compute='_compute_display_invoice_amount_warning')

    consolidated_billing = fields.Boolean(
        string='Consolidated Billing',
        default=True,
        help='Create one invoice for all orders related to same customer and same invoicing address',
    )

    date_start_invoice_timesheet = fields.Date(
        string='Start Date',
        help='Only timesheets not yet invoiced (and validated, if applicable) from this period will be invoiced. '
        'If the period is not indicated, all timesheets not yet invoiced (and validated, if applicable)'
        'will be invoiced without distinction.',
    )
    date_end_invoice_timesheet = fields.Date(
        string='End Date',
        help='Only timesheets not yet invoiced (and validated, if applicable) from this period will be invoiced. '
        'If the period is not indicated, all timesheets not yet invoiced (and validated, if applicable) '
        'will be invoiced without distinction.',
    )
    invoicing_timesheet_enabled = fields.Boolean(compute='_compute_invoicing_timesheet_enabled')

    @api.depends('sale_order_ids')
    def _compute_invoicing_timesheet_enabled(self):
        if not self.env['ir.module.module']._get('sale_timesheet').state == 'installed':
            self.invoicing_timesheet_enabled = False
            return

        for wizard_id in self:
            # noinspection PyUnresolvedReferences
            wizard_id.invoicing_timesheet_enabled = bool(
                wizard_id.sale_order_ids.order_line.filtered(
                    lambda _sol_id: _sol_id.invoice_status == 'to invoice'
                ).product_id.filtered(lambda _p_id: _p_id._is_delivered_timesheet())
            )

    @api.depends('sale_order_ids')
    def _compute_currency_fields(self):
        for wizard_id in self:
            if len(wizard_id.sale_order_ids.company_id) > 1:
                raise UserError(_('Sale orders from multiple companies!'))

            wizard_id.company_id = wizard_id.sale_order_ids.company_id

            if len(wizard_id.sale_order_ids.currency_id) > 1:
                raise UserError(_('Sale orders with multiple currencies!'))

            wizard_id.currency_id = wizard_id.sale_order_ids.currency_id
            wizard_id.is_convertible = wizard_id.currency_id != wizard_id.company_id.currency_id

    @api.depends('sale_order_ids')
    def _compute_dynamic_fields(self):
        for wizard_id in self:
            wizard_id.sale_order_count = len(wizard_id.sale_order_ids)
            wizard_id.has_down_payments = bool(wizard_id.sale_order_ids.order_line.filtered('is_downpayment'))
            wizard_id.amount_invoiced = sum(wizard_id.sale_order_ids._origin.mapped('amount_invoiced'))
            # wizard_id.amount_to_invoice = sum(wizard_id.sale_order_ids._origin.mapped('amount_to_invoice'))
            wizard_id.amount_to_invoice = sum(wizard_id.sale_order_ids.mapped('amount_to_invoice'))

    @api.depends('sale_order_ids')
    def _compute_display_draft_invoice_warning(self):
        for wizard_id in self:
            wizard_id.display_draft_invoice_warning = wizard_id.sale_order_ids.invoice_ids.filtered(
                lambda invoice_id: invoice_id.state == 'draft'
            )

    @api.depends('sale_order_ids.order_line')
    def _compute_invoice_line_ids(self):
        for wizard_id in self:
            wizard_id.invoice_line_ids = [
                Command.set(
                    wizard_id.sale_order_ids.order_line.filtered(lambda l_id: l_id.invoice_status == 'to invoice').ids
                )
            ]

    def _inverse_invoice_line_ids(self):
        pass

    @api.onchange('convert_to_local')
    def _onchange_convert_to_local(self):
        if not self.convert_to_local:
            self.convert_rate_id = False

    @api.depends('advance_line_ids.amount_total', 'invoice_type', 'amount_to_invoice')
    def _compute_display_invoice_amount_warning(self):
        for wizard_id in self:
            if wizard_id.advance_line_ids:
                invoice_amount = sum(wizard_id.advance_line_ids._origin.mapped('amount_total'))
                wizard_id.display_invoice_amount_warning = (
                    wizard_id.invoice_type == 'advance'
                    and wizard_id.currency_id.compare_amounts(invoice_amount, wizard_id.amount_to_invoice) > 0
                )

            else:
                wizard_id.display_invoice_amount_warning = False

    @api.onchange('allowed_partner_bank_ids')
    @api.depends('allowed_partner_bank_ids')
    def _x_onchange_set_partner_bank_account(self):
        self.partner_bank_id = fields.first(self.allowed_partner_bank_ids)

    @api.depends('currency_id', 'convert_to_local', 'company_id')
    def _compute_allowed_partner_bank_accounts(self):
        for wizard_id in self:
            wizard_currency_id = (
                wizard_id.convert_to_local and wizard_id.company_id.currency_id or wizard_id.currency_id
            )

            wizard_id.allowed_partner_bank_ids = [
                Command.set(
                    wizard_id.company_id.partner_id.bank_ids.filtered(
                        lambda bank_id: bank_id.currency_id == wizard_currency_id
                    ).ids
                )
            ]

    @api.depends('invoice_type', 'sale_order_ids')
    def _compute_advance_line_ids(self):
        for wizard_id in self:
            tax_map = defaultdict(lambda: {'so_amount': 0, 'so_amount_total': 0})

            for line_id in wizard_id.filtered(
                lambda w_id: w_id.invoice_type == 'advance'
            ).sale_order_ids.order_line.filtered(lambda l_id: not l_id.display_type):
                tax_map[(line_id.tax_id._origin.id, wizard_id.currency_id.id)]['so_amount'] += line_id.price_subtotal
                tax_map[(line_id.tax_id._origin.id, wizard_id.currency_id.id)]['so_amount_total'] += (
                    wizard_id.currency_id.round(line_id.price_total)
                )

            wizard_id.advance_line_ids = [Command.clear()] + [
                Command.create({'tax_id': tax, 'currency_id': currency} | record)
                for (tax, currency), record in tax_map.items()
            ]

    def _inverse_advance_line_ids(self):
        pass

    def _check_down_payment_product_is_valid(self):
        down_payment_product_id = self.company_id.x_sale_down_payment_product_id

        if not down_payment_product_id:
            raise UserError(_('Down payment product is not configured.'))

        if down_payment_product_id.invoice_policy != 'order':
            raise UserError(
                _(
                    'The product used to invoice a down payment should have an invoice policy set to '
                    '"Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'
                )
            )

        if down_payment_product_id.type != 'service':
            raise UserError(
                _(
                    "The product used to invoice a down payment should be of type 'Service'. Please use another "
                    'product or update this product.'
                )
            )

    def _prepare_invoice_values(self, order_id, so_line_ids):
        self.ensure_one()

        context = {'lang': order_id.partner_invoice_id.lang or order_id.partner_id.lang}

        invoice_vals = order_id._prepare_invoice() | {
            'partner_bank_id': self.partner_bank_id.id,
            'invoice_line_ids': [Command.create(l_id._prepare_invoice_line(quantity=1.0)) for l_id in so_line_ids],
        }

        if not invoice_vals.get('x_invoice_sale_date'):
            invoice_vals['x_invoice_sale_date'] = fields.Date.context_today(order_id)

        if self.convert_to_local:
            invoice_vals['currency_id'] = self.company_id.currency_id.id

            if self.convert_rate_id:
                if narration := invoice_vals.get('narration', ''):
                    narration += Markup('<br/>')

                narration += _(
                    'Rate %s with effective date: %s',
                    self.convert_rate_id.inverse_company_rate,
                    self.convert_rate_id.name,
                )

                invoice_vals['narration'] = narration

        del context

        return invoice_vals

    def _prepare_down_payment_lines_values(self, sale_order_ids):
        self.ensure_one()

        order_line_ids = sale_order_ids.order_line.filtered(
            lambda l_id: not l_id.display_type and not l_id.is_downpayment
        )

        analytic_distribution = defaultdict(float)
        amount_total = sum(order_line_ids.mapped('price_total'), 0.0)

        if not self.currency_id.is_zero(amount_total):
            for line_id in order_line_ids:
                for account, distribution in (line_id.analytic_distribution or {}).items():
                    analytic_distribution[account] += distribution * line_id.price_total

            for account, distribution_amount in analytic_distribution.items():
                analytic_distribution[account] = distribution_amount / amount_total

        # noinspection PyUnusedLocal
        context = {'lang': sale_order_ids.partner_invoice_id.lang or sale_order_ids.partner_id.lang}
        self = self.with_context(**context)

        so_values = [
            line_id.prepare_downpayment_so_line(sale_order_ids)
            | {
                'analytic_distribution': analytic_distribution,
                'sequence': (sale_order_ids.order_line and sale_order_ids.order_line[-1].sequence or 10) + line_idx,
            }
            for line_idx, line_id in enumerate(
                self.advance_line_ids.filtered(lambda l_id: not l_id.currency_id.is_zero(l_id.amount_total)), 1
            )
        ]

        return so_values

    # noinspection PyMethodMayBeStatic
    def _prepare_down_payment_section_values(self, sale_order_id):
        sale_order_id.ensure_one()

        context = {'lang': sale_order_id.partner_invoice_id.lang or sale_order_id.partner_id.lang}

        so_values = {
            'name': _('Down Payments'),
            'product_uom_qty': 0.0,
            'order_id': sale_order_id.id,
            'display_type': 'line_section',
            'is_downpayment': True,
            'sequence': sale_order_id.order_line and sale_order_id.order_line[-1].sequence + 1 or 10,
        }

        del context

        return so_values

    def _create_invoices(self, sale_order_ids):
        self.ensure_one()

        if len(sale_order_ids.partner_invoice_id) > 1:
            raise UserError(_('Creating single invoice for multiple partners is not supoprted.'))

        context = {
            'x_advance': True,  # mark that this is an advance wizard
            'x_journal_id': self.journal_id.id,
            'x_convert_rate_id': self.convert_rate_id.id if self.convert_rate_id else None,
            'x_partner_bank_id': self.partner_bank_id.id,
            'lang': sale_order_ids.partner_invoice_id.lang,
        }

        self = self.with_company(self.company_id).with_context(**context)
        sale_order_ids = sale_order_ids.with_context(**context)

        if self.invoice_type == 'normal':
            if self.invoicing_timesheet_enabled:
                if self.date_start_invoice_timesheet or self.date_end_invoice_timesheet:
                    sale_order_ids.order_line._recompute_qty_to_invoice(
                        self.date_start_invoice_timesheet, self.date_end_invoice_timesheet
                    )
                return sale_order_ids.with_context(
                    **(
                        context
                        | {
                            'selected_invoice_lines': self.invoice_line_ids.ids,
                            'timesheet_start_date': self.date_start_invoice_timesheet,
                            'timesheet_end_date': self.date_end_invoice_timesheet,
                        }
                    )
                )._create_invoices(grouped=not self.consolidated_billing, final=True)
            return sale_order_ids.with_context(selected_invoice_lines=self.invoice_line_ids.ids)._create_invoices(
                grouped=not self.consolidated_billing, final=True
            )

        self._check_down_payment_product_is_valid()

        sale_order_ids.ensure_one()

        down_payment_line_ids = self.env['sale.order.line'].with_context(sale_no_log_for_new_lines=True, **context)

        # Create a down payment section if necessary
        if not any(line.display_type and line.is_downpayment for line in sale_order_ids.order_line):
            down_payment_line_ids.create(self._prepare_down_payment_section_values(sale_order_ids))

        down_payment_line_ids = down_payment_line_ids.create(self._prepare_down_payment_lines_values(sale_order_ids))

        invoice_id = (
            self.env['account.move'].sudo().create(self._prepare_invoice_values(sale_order_ids, down_payment_line_ids))
        )

        # Un-sudo the invoice after creation if not already sudo-ed
        invoice_id = invoice_id.sudo(self.env.su)

        poster = self.env.user._is_internal() and self.env.user.id or SUPERUSER_ID
        invoice_id.with_user(poster).message_post_with_source(
            'mail.message_origin_link',
            render_values={'self': invoice_id, 'origin': sale_order_ids},
            subtype_xmlid='mail.mt_note',
        )

        sale_order_ids.with_user(poster).message_post(
            body=_('%s has been created', invoice_id._get_html_link(title=_('Down payment invoice')))
        )

        return invoice_id

    def _check_amount_is_positive(self):
        for wizard_id in self:
            if (
                wizard_id.invoice_type == 'advance'
                and wizard_id.currency_id.compare_amounts(sum(wizard_id.advance_line_ids.mapped('amount')), 0.0) <= 0
            ):
                raise UserError(_('The value of the down payment amount must be positive.'))

    def create_invoices(self):
        self._check_amount_is_positive()
        return self.sale_order_ids.action_view_invoice(invoices=self._create_invoices(self.sale_order_ids))

    def view_draft_invoices(self):
        return {
            'name': _('Draft Invoices'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'views': [(False, 'list'), (False, 'form')],
            'res_model': 'account.move',
            'domain': [('line_ids.sale_line_ids.order_id', 'in', self.sale_order_ids.ids), ('state', '=', 'draft')],
        }


class InvoiceWizardLine(models.TransientModel):
    _name = 'trilab.invoice.wizard.line'
    _description = 'Sale Advance Line'

    wizard_id = fields.Many2one('trilab.invoice.wizard', required=True)
    tax_id = fields.Many2one('account.tax', required=True)
    so_amount = fields.Monetary(string='SO Amount [NET]')
    so_amount_total = fields.Monetary(string='SO Amount [GROSS]')
    amount = fields.Monetary(required=False, string='Amount [NET]')
    amount_total = fields.Monetary(required=False, string='Amount [GROSS]')
    percent = fields.Float(required=False, string='Value Percent')
    currency_id = fields.Many2one('res.currency', string='Currency')
    company_currency_id = fields.Many2one(related='wizard_id.company_id.currency_id', string='Company Currency')
    convert_to_local = fields.Boolean(related='wizard_id.convert_to_local')
    convert_rate_id = fields.Many2one(related='wizard_id.convert_rate_id')

    @api.constrains('amount', 'percent')
    def constrains_values(self):
        for line_id in self:
            if line_id.wizard_id.invoice_type == 'normal':
                continue

            # can't use float_compare as we do not have precision
            if line_id.percent < 0.0:
                raise UserError(_('Percent Value must be positive'))

            if line_id.percent > 100.0:
                raise UserError(_('Percent Value cannot be greater than 100%'))

            if line_id.currency_id.compare_amounts(line_id.amount, 0.0) == -1:
                raise UserError(_('Advance line value must be positive'))

            # rounding issue #4245
            if line_id.currency_id.compare_amounts(line_id.amount_total - line_id.so_amount_total, 0.05) > 0:
                raise UserError(_('Advance line value is bigger than order value'))

    @api.depends(
        'amount',
        'so_amount_total',
        'currency_id',
        'company_currency_id',
        'wizard_id.convert_to_local',
        'wizard_id.convert_rate_id',
    )
    def _compute_local(self):
        for line_id in self:
            if line_id.wizard_id.convert_to_local:
                line_id.amount_local = line_id.currency_id.round(
                    line_id.amount * (line_id.wizard_id.convert_rate_id.inverse_company_rate or 1.0)
                )
                line_id.amount_total_local = line_id.currency_id.round(
                    line_id.amount_total * (line_id.wizard_id.convert_rate_id.inverse_company_rate or 1.0)
                )
            else:
                line_id.amount_local = line_id.amount
                line_id.amount_total_local = line_id.amount_total

    @api.onchange('amount')
    def onchange_amount(self):
        if (update_pct := self.env.context.get('percent')) or self.env.context.get('amount'):
            self.amount_total = self.tax_id.compute_all(
                self.amount, currency=self.currency_id, handle_price_include=False
            )['total_included']

            if not update_pct:
                self.percent = (self.amount / self.so_amount) * 100.0

    @api.onchange('amount_total')
    def onchange_amount_total(self):
        if self.env.context.get('amount_total'):
            self.amount = self.tax_id.with_context(force_price_include=True).compute_all(
                self.amount_total, currency=self.currency_id
            )['total_excluded']
            self.percent = (self.amount / self.so_amount) * 100.0

    @api.onchange('percent')
    def onchange_percent(self):
        if self.env.context.get('percent'):
            self.amount = self.currency_id.round(self.so_amount * (self.percent / 100.0))
            # amount_total updated by onchange_amount
            # self.amount_total = self.currency_id.round(self.amount * (1.0 + (self.tax_id.amount / 100.0)))

    def prepare_downpayment_so_line(self, sale_order_id):
        self.ensure_one()

        # noinspection PyUnusedLocal
        context = {'lang': sale_order_id.partner_invoice_id.lang or sale_order_id.partner_id.lang}
        self = self.with_context(**context)

        if self.tax_id.price_include:
            price_unit = self.tax_id.compute_all(self.amount_total, currency=self.currency_id)['total_included']
        else:
            price_unit = self.tax_id.compute_all(self.amount, currency=self.currency_id)['total_excluded']

        values = {
            'name': f'[{self.tax_id.name}]',
            'price_unit': price_unit,
            'product_uom_qty': 0.0,
            'order_id': sale_order_id.id,
            'discount': 0.0,
            'product_id': self.wizard_id.company_id.x_sale_down_payment_product_id.id,
            'is_downpayment': True,
            'tax_id': [Command.set(self.tax_id.ids)],
        }

        return values
