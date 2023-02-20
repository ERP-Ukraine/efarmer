# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from odoo.tools import float_round


class Employee(models.Model):
    _inherit = 'hr.employee'


    employee_type = fields.Selection(
        selection_add=[('outstaff', 'Outstaff')],
        ondelete={'outstaff': 'set default'}
    )

    salary_type = fields.Selection(
        selection=[
            ('salary', 'Salary'),
            ('hourly', 'Hourly'),
            ('commission', 'Commision Only'),
        ],
        string='Salary Type',
        # readonly=True,
    )

    pay_rate = fields.Float(
        string='Pay Rate',
        # readonly=True,
    )

    paid_per = fields.Selection(
        selection=[
            ('day', 'Day'),
            ('week', 'Week'),
            ('month', 'Month'),
            ('quarter', 'Quarter'),
            ('year', 'Year'),
            ('pay_period', 'Pay Period'),
            ('piece', 'Piece'),
            ('hour', 'Hour'),
        ],
        string='Paid Per',
        # readonly=True,
    )

    med_insurance_rate = fields.Float(
        string='Medical Insurance Rate',
        # readonly=True,
    )

    ann_gross_salary = fields.Monetary(
        string='Annual Gross Salary',
        currency_field='currency_id',
        # digits=(16, 2),
    )

    ann_payroll_tax = fields.Monetary(
        string='Annual Payroll Tax Cost to Employer',
        currency_field='currency_id',
        # digits=(16, 2),
    )

    ann_med_insurance_cost = fields.Monetary(
        string='Annual Medical Insurance Costs',
        currency_field='currency_id',
        # digits=(16, 2),
    )

    ann_bonus = fields.Monetary(
        string='Annual Bonus',
        currency_field='currency_id',
        # digits=(16, 2),
    )

    other_allowances = fields.Monetary(
        string='Other Allowances',
        currency_field='currency_id',
        # digits=(16, 2),
    )

    bamboo_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency", 
    )

    def compute_timesheet_cost(self, company_id):
        employees = self.search([
            ('company_id', '=', company_id),
            ('employee_type', 'in', ['employee', 'contractor', 'outstaff'])])

        for employee in employees:
            if employee.employee_type == 'employee':
                cost_values = [employee.ann_gross_salary, employee.ann_payroll_tax,
                    employee.ann_med_insurance_cost, employee.ann_bonus, employee.other_allowances]
                annual_ts_cost = sum(cost_values)
                # work_hours = employee._get_work_days_data_batch(datetime(2023,1,1), datetime(2023,12,31), calendar=employee.resource_calendar_id)
        
        