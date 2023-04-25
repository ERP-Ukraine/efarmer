# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPurchaseWorkflow(TransactionCase):
    def setUp(self):
        super(TestPurchaseWorkflow, self).setUp()

        self.fin_manager = self.env['res.users'].create({
            'name': 'Financial Manager',
            'login': 'fin_manager',
            'email': 'test@company.com',
        })
        self.po_manager_user = self.env['res.users'].create({
            'name': 'Purchase Manager',
            'login': 'po_manager',
            'email': 'test@company.com',
        })
        self.po_manager_employee = self.env['hr.employee'].create({
            'name': 'Purchase Manager Employee',
            'user_id': self.po_manager_user.id,
        })
        self.dep = self.env['hr.department'].create({
            'name': 'Test Dep',
        })
        self.po_user = self.env['res.users'].create({
            'name': 'Purchase User',
            'login': 'po_user',
            'email': 'test@company.com',
        })
        self.po_employee = self.env['hr.employee'].create({
            'name': 'Purchase Employee',
            'user_id': self.po_user.id,
            'department_id': self.dep.id,
        })
        self.day_add_vals = {1: 1, 2: 1, 3: 1, 4: 1, 5: 3, 6: 2, 7: 1}

        self.partner = self.env.ref('base.main_partner')
        self.product = self.env['product.product'].create({'name': 'Test Product'})
        self.purchase_order = self.env['purchase.order'].with_user(self.po_user.id).create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {
                    'name': self.product.name,
                    'product_id': self.product.id,
                    'product_qty': 1.0,
                    'product_uom': self.product.uom_po_id.id,
                    'price_unit': 100.0,
                })],
        })

    def test_purchase_confirm_rfq(self):
        # confirm RFQ without defining manager_id for employee department
        with self.assertRaises(UserError):
            self.purchase_order.action_confirm_rfq()

        self.dep.manager_id = self.po_manager_employee.id
        self.purchase_order.action_confirm_rfq()

        self.assertEqual(self.purchase_order.state, 'confirm_demand')

        # expect that scheduled action for po_manager was created
        scheduled_activity = self.env['mail.activity'].search([
            ('user_id', '=', self.po_manager_user.id)
        ])
        self.assertIsNotNone(scheduled_activity)

        today = date.today()
        expected_date = today + timedelta(
            days=self.day_add_vals.get(today.isoweekday())
        )
        self.assertEqual(scheduled_activity.date_deadline, expected_date)

    def test_purchase_confirm_demand_group_all(self):
        self.purchase_order.state = 'confirm_demand'

        # confirm Demand without allow_confirm_demand_all group
        with self.assertRaises(UserError):
            self.purchase_order.action_confirm_demand()

        self.po_user.write({'groups_id': [(
            4, self.env.ref('efarmer_purchase.efarmer_purchase_allow_confirm_demand_all').id
        )]})
        self.purchase_order.action_confirm_demand()
        self.assertEqual(self.purchase_order.state, 'fin_approve')

    def test_purchase_confirm_demand_manager(self):
        self.purchase_order.state = 'confirm_demand'
        self.dep.manager_id = self.po_manager_employee.id
        self.env.company.write({'fin_manager_id': self.fin_manager.id})

        # confirm Demand by po_user, not po_manager
        with self.assertRaises(UserError):
            self.purchase_order.action_confirm_demand()

        self.purchase_order.with_user(self.po_manager_user.id).action_confirm_demand()
        self.assertEqual(self.purchase_order.state, 'fin_approve')

        # expect that scheduled action for fin_manager was created
        scheduled_activity = self.env['mail.activity'].search([
            ('user_id', '=', self.fin_manager.id)
        ])
        self.assertIsNotNone(scheduled_activity)
