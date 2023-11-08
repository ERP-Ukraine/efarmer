# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, _, api
from odoo.exceptions import UserError

from datetime import date, timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    amount_total_in_eur = fields.Float(
        string="Amount Total in EUR",
        store=True,
        compute='_compute_amount_total_in_eur',
    )
    untaxed_amount_in_eur = fields.Float(
        string="Untaxed Amount in EUR",
        store=True,
        compute='_compute_untaxed_amount_in_eur',
    )
    residual_amount_in_eur = fields.Float(
        string="Residual Amount in EUR",
        store=True,
        compute='_compute_residual_amount_in_eur',
    )

    state = fields.Selection(
        selection_add=[
            ('confirm_demand', 'Confirm Demand'),
            ('fin_approve', 'Financial Approval'),
            ('purchase',)
        ],
    )

    analytic_tag_ids = fields.Many2many(
        comodel_name='account.analytic.tag',
        string='Analytic Tags',
        compute='_compute_purchase_analytic_tag_ids',
    )

    def __get_default_currency(self):
        currency_pln = self.env['res.currency'].search([('name', '=', 'EUR')])
        default_rate = currency_pln.rate_ids.filtered(
            lambda x: x.company_id == self.company_id
        ).sorted(key='name', reverse=True)[0].inverse_company_rate

        return default_rate

    @api.depends('amount_total')
    def _compute_amount_total_in_eur(self):
        for record in self:
            record.amount_total_in_eur = record.amount_total * record.__get_default_currency()

    @api.depends('amount_untaxed')
    def _compute_untaxed_amount_in_eur(self):
        for record in self:
            record.untaxed_amount_in_eur = record.amount_untaxed * record.__get_default_currency()

    @api.depends('amount_residual')
    def _compute_residual_amount_in_eur(self):
        for record in self:
            record.residual_amount_in_eur = record.amount_residual * record.__get_default_currency()

    def _compute_purchase_analytic_tag_ids(self):
        for po in self:
            po.analytic_tag_ids = po.order_line.mapped('analytic_tag_ids')

    def _get_next_weekday(self, date):
        """
        Returns the next weekday (Monday to Friday).
        If the next day is Saturday or Sunday, returns Monday.
        """
        days_to_add = 1
        if date.isoweekday() in set((5, 6)):
            days_to_add = 8 - date.isoweekday()
        next_day = date + timedelta(days=days_to_add)
        return next_day

    def _get_department_manager(self):
        po_employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', self.user_id.id)], limit=1
        )
        manager = po_employee.department_id.manager_id
        if not manager:
            raise UserError(_(
                'Manager for the department "{}" is not set.\n'
                'Please, ask your administrator to set up manager for the department.'.format(
                    po_employee.department_id.name
                )
            ))
        return manager

    def create_po_activity(self, summary, user, date_deadline=None, activity_type_id=None):
        if not date_deadline:
            date_deadline = self._get_next_weekday(date.today())
        if not activity_type_id:
            activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        self.activity_schedule(
            date_deadline=date_deadline,
            activity_type_id=activity_type_id,
            summary=summary,
            user_id=user.id,
        )

    def action_confirm_rfq(self):
        self.write({'state': 'confirm_demand'})
        user_to_notify = self._get_department_manager().user_id
        self.create_po_activity(
            'Confirm Demand for {}'.format(self.name),
            user_to_notify
        )
    
    def action_confirm_demand(self):
        group_confirm_all = 'efarmer_purchase.efarmer_purchase_allow_confirm_demand_all'
        if not self.env.user.has_group(group_confirm_all):
            allow_confirm_user = self._get_department_manager().user_id
            if self.env.user != allow_confirm_user:
                raise UserError(_(
                    'You are not allowed to Confirm Demand for this department.\n'
                    'Contact the manager of department to confirm.'
                ))
        self.write({'state': 'fin_approve'})
        self.create_po_activity(
            'Approve Financial for {}'.format(self.name),
            self.env.company.fin_manager_id
        )

    def button_confirm(self):
        """
        Override standart method to have possibility to confirm PO
        also in 'Financial Approval' state
        """
        for order in self:
            if order.state not in ['draft', 'sent', 'fin_approve']:
                continue
            order._add_supplier_to_product()
            # Deal with double validation process
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        return True
