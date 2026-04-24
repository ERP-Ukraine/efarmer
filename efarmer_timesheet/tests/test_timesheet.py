# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from unittest.mock import patch
from odoo.tests import TransactionCase


class TestHrTimesheet(TransactionCase):

    def setUp(self):
        super(TestHrTimesheet, self).setUp()

        self.company = self.env["res.company"].create(
            {"name": "Test Company", "currency_id": self.env.ref("base.USD").id}
        )

        self.mock_work_hours = self._create_patch_object(
            type(self.env["hr.employee"]), "_get_work_days_data_batch"
        )
        self.employee_obj = self.env["hr.employee"]

    def _create_patch_object(self, target, attribute):
        patcher = patch.object(target, attribute)
        thing = patcher.start()
        self.addCleanup(patcher.stop)
        return thing

    def test_compute_employee_timesheet_cost(self):
        """
        Testing the logic calculation of employee Timesheet Cost.
        """
        employee = self.employee_obj.create(
            {
                "name": "Test Employee",
                "employee_type": "employee",
                "company_id": self.company.id,
                "ann_gross_salary": 30000.00,
                "ann_payroll_tax": 100.00,
                "ann_med_insurance_cost": 50.00,
                "ann_bonus": 70.00,
                "other_allowances": 200.00,
            }
        )

        self.mock_work_hours.return_value = {employee.id: {"hours": 2008.0}}

        mock_employee_search = self._create_patch_object(
            type(self.employee_obj), "search"
        )
        # define the search results in compute_timesheet_cost() to avoid existing
        # employees being included in the search results.
        mock_employee_search.side_effect = [employee, self.employee_obj]

        # expected res: (30000 + 100 + 50 + 70 + 200) / 2008 = 15.15
        employee.compute_timesheet_cost()

        self.assertEqual(employee.hourly_cost, 15.15)

    def test_compute_outstaff_timesheet_cost(self):
        outstaff = self.employee_obj.create(
            {
                "name": "Test Outstaff",
                "paid_per": "month",
                "employee_type": "outstaff",
                "company_id": self.company.id,
                "bamboo_currency_id": self.env.ref("base.EUR").id,
                "pay_rate": 1000.00,
            }
        )
        self.mock_work_hours.return_value = {outstaff.id: {"hours": 2008.0}}

        mock_currency = self._create_patch_object(
            type(self.env["res.currency"]), "_get_conversion_rate"
        )
        mock_currency.return_value = 1.2

        mock_employee_search = self._create_patch_object(
            type(self.employee_obj), "search"
        )

        # define the search results in compute_timesheet_cost() to avoid existing
        # employees being included in the search results.
        mock_employee_search.side_effect = [
            outstaff,
            self.employee_obj,
            outstaff,
            self.employee_obj,
            outstaff,
            self.employee_obj,
            self.employee_obj,
            outstaff,
        ]

        # expected res: (1000 * 1.2 * 12) / 2008 = 7.17
        outstaff.compute_timesheet_cost()
        self.assertEqual(outstaff.hourly_cost, 7.17)

        outstaff.paid_per = "year"
        outstaff.pay_rate = 50000.00

        # expected res: (50000 * 1.2) / 2008 = 29.88
        outstaff.compute_timesheet_cost()
        self.assertEqual(outstaff.hourly_cost, 29.88)

        outstaff.paid_per = "hour"
        outstaff.pay_rate = 30.00
        outstaff.bamboo_currency_id = outstaff.company_id.currency_id.id

        # expected res: 30
        outstaff.compute_timesheet_cost()
        self.assertEqual(outstaff.hourly_cost, 30)

        outstaff.paid_per = "day"

        # expected res: 0
        outstaff.compute_timesheet_cost()
        self.assertEqual(outstaff.hourly_cost, 0)

        # expect to get 2 calls, when employee currency_id and bamboo_currency_id were different
        self.assertEqual(mock_currency.call_count, 2)

    def test_create_timesheet(self):
        employee = self.env["hr.employee"].create(
            {
                "name": "Test Employee",
                "company_id": self.company.id,
                "hourly_cost": 80,
            }
        )
        project = self.env["project.project"].create(
            {
                "name": "Test Project",
                "company_id": self.company.id,
            }
        )
        timesheet = self.env["account.analytic.line"].create(
            {
                "name": "Test Timesheet",
                "employee_id": employee.id,
                "project_id": project.id,
            }
        )

        self.assertEqual(timesheet.rate_per_hour, 80)
