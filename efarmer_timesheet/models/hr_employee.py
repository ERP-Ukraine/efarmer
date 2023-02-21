# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime

from odoo import fields, models


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
        copy=False,
    )

    pay_rate = fields.Float(
        string='Pay Rate',
        copy=False,
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
        copy=False,
    )

    med_insurance_rate = fields.Float(
        string='Medical Insurance Rate',
        copy=False,
    )

    ann_gross_salary = fields.Monetary(
        string='Annual Gross Salary',
        currency_field='currency_id',
        copy=False,
    )

    ann_payroll_tax = fields.Monetary(
        string='Annual Payroll Tax Cost to Employer',
        currency_field='currency_id',
        copy=False,
    )

    ann_med_insurance_cost = fields.Monetary(
        string='Annual Medical Insurance Costs',
        currency_field='currency_id',
        copy=False,
    )

    ann_bonus = fields.Monetary(
        string='Annual Bonus',
        currency_field='currency_id',
        copy=False,
    )

    other_allowances = fields.Monetary(
        string='Other Allowances',
        currency_field='currency_id',
        copy=False,
    )

    bamboo_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Currency",
        copy=False,
        default=lambda self: self.env.company.currency_id.id
    )

    def compute_timesheet_cost(self):
        """ Calculate Timesheet Cost only for employees with type 'employee'
        and employees with type 'contractor'/'outstaff' and
        'year', 'month', 'hour' periods of payment
        """
        all_empls = self.search([])
        paid_periods = ['year', 'month', 'hour']
        empls_to_compute = all_empls.filtered(lambda empl: empl.employee_type == 'employee'
            or (empl.employee_type in ['contractor', 'outstaff'] and empl.paid_per in paid_periods))

        if empls_to_compute:
            current_year = datetime.today().year
            year_start = datetime(current_year, 1, 1)
            year_end = datetime(current_year, 12, 31)

            for employee in empls_to_compute:
                # get work hours
                work_time_data = employee._get_work_days_data_batch(
                    year_start, year_end, calendar=employee.resource_calendar_id)[employee.id]
                work_hours = work_time_data.get('hours', 0)
                ts_cost_value = 0
                # set 0 cost if employee hasn't working hours to avoid ZeroDivisionError
                if not work_hours:
                    employee.timesheet_cost = ts_cost_value
                    continue

                # compute cost for employees
                if employee.employee_type == 'employee':
                    cost_values = [employee.ann_gross_salary, employee.ann_payroll_tax,
                        employee.ann_med_insurance_cost, employee.ann_bonus, employee.other_allowances]
                    annual_ts_cost = sum(cost_values)
                    ts_cost_value = annual_ts_cost / work_hours
                else:
                    # get currency rate
                    currency_rate = 1
                    if employee.bamboo_currency_id != employee.currency_id:
                        currency_rate = self.env['res.currency']._get_conversion_rate(
                            employee.bamboo_currency_id,
                            employee.currency_id,
                            employee.company_id,
                            fields.Date.today()
                        )
                    # compute cost for contractors and outstaffs
                    if employee.paid_per == 'year':
                        ts_cost_value = employee.pay_rate * currency_rate / work_hours
                    elif employee.paid_per == 'month':
                        ts_cost_value = employee.pay_rate * currency_rate * 12 / work_hours
                    elif employee.paid_per == 'hour':
                        ts_cost_value = employee.pay_rate * currency_rate

                employee.timesheet_cost = ts_cost_value

        # update employees that had timesheet cost but now has employee_type or paid_per
        # that not provide calculation of timesheet cost
        empls_to_update = (all_empls - empls_to_compute).filtered(lambda empl: empl.timesheet_cost != 0.00)
        if empls_to_update:
            for employee in empls_to_update:
                employee.timesheet_cost = 0
