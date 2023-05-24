# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, _
from odoo.exceptions import UserError

from datetime import date, timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(
        selection_add=[
            ('confirm_demand', 'Confirm Demand'),
            ('purchase',)
        ],
    )

    # Override to remove default value
    date_order = fields.Datetime(
        default=False,
    )

    analytic_tag_ids = fields.Many2many(
        comodel_name='account.analytic.tag',
        string='Analytic Tags',
        compute='_compute_purchase_analytic_tag_ids',
    )

    def _compute_purchase_analytic_tag_ids(self):
        for po in self:
            if po.order_line:
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

    def button_confirm(self):
        """
        Override standart method to have possibility to confirm PO
        also in 'Confirm Demand' state
        """
        for order in self:
            if order.state not in ['draft', 'sent', 'confirm_demand']:
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
