# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime

from odoo import fields, models


class Employee(models.Model):
    _inherit = "hr.employee"

    # employee_type = fields.Selection(
    #     selection_add=[('outstaff', 'Outstaff')],
    #     ondelete={'outstaff': 'set default'}
    # )

    salary_type = fields.Selection(
        selection=[
            ("salary", "Salary"),
            ("hourly", "Hourly"),
            ("commission", "Commision Only"),
        ],
        string="Salary Type",
        copy=False,
        groups="hr.group_hr_user",
    )

    pay_rate = fields.Float(
        string="Pay Rate",
        copy=False,
        groups="hr.group_hr_user",
    )

    paid_per = fields.Selection(
        selection=[
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
            ("pay_period", "Pay Period"),
            ("piece", "Piece"),
            ("hour", "Hour"),
        ],
        string="Paid Per",
        copy=False,
        groups="hr.group_hr_user",
    )

    med_insurance_rate = fields.Float(
        string="Medical Insurance Rate",
        copy=False,
        groups="hr.group_hr_user",
    )

    ann_gross_salary = fields.Monetary(
        string="Annual Gross Salary",
        currency_field="currency_id",
        copy=False,
        groups="hr.group_hr_user",
    )

    ann_payroll_tax = fields.Monetary(
        string="Annual Payroll Tax Cost to Employer",
        currency_field="currency_id",
        copy=False,
        groups="hr.group_hr_user",
    )

    ann_med_insurance_cost = fields.Monetary(
        string="Annual Medical Insurance Costs",
        currency_field="currency_id",
        copy=False,
        groups="hr.group_hr_user",
    )

    ann_bonus = fields.Monetary(
        string="Annual Bonus",
        currency_field="currency_id",
        copy=False,
        groups="hr.group_hr_user",
    )

    other_allowances = fields.Monetary(
        string="Other Allowances",
        currency_field="currency_id",
        copy=False,
        groups="hr.group_hr_user",
    )

    bamboo_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        copy=False,
        default=lambda self: self.env.company.currency_id.id,
        groups="hr.group_hr_user",
    )

    contract_pay_rate = fields.Monetary(
        string="Contract Pay Rate", currency_field="bamboo_currency_id", default=0.0
    )

    account_asset_counterpart_id = fields.Many2one(
        "account.account",
        string="Account Asset Counterpart",
        check_company=True,
        help="Account used as counterpart for entries related to this asset.",
        tracking=True,
        store=True,
    )

    related_contact_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
    )

    def compute_timesheet_cost(self):
        """Calculate Timesheet Cost (hourly_cost) only for employees with type
        'employee' and employees with type 'contractor'/'outstaff'
        and 'year', 'month', 'hour' periods of payment.
        Set Timesheet Cost = 0 if above parameters were changed for employee.
        """
        empls_to_compute = self.search(
            [
                "|",
                ("employee_type", "=", "employee"),
                "&",
                ("employee_type", "in", ["contractor", "outstaff"]),
                ("paid_per", "in", ["year", "month", "hour"]),
            ]
        )

        if empls_to_compute:
            current_year = datetime.today().year
            year_start = datetime(current_year, 1, 1)
            year_end = datetime(current_year, 12, 31)
            work_time_data_ids = empls_to_compute._get_work_days_data_batch(
                year_start, year_end
            )

            for employee in empls_to_compute:
                # get work hours
                work_time_data = work_time_data_ids[employee.id]
                work_hours = work_time_data.get("hours", 0)
                ts_cost_value = 0
                contract_cost_value = 0
                # set 0 cost if employee hasn't working hours to avoid ZeroDivisionError
                if not work_hours:
                    employee.hourly_cost = ts_cost_value
                    employee.contract_pay_rate = contract_cost_value
                    continue

                # compute cost for employees
                if employee.employee_type == "employee":
                    annual_ts_cost = employee.mapped(
                        lambda x: x.ann_gross_salary
                        + x.ann_payroll_tax
                        + x.ann_med_insurance_cost
                        + x.ann_bonus
                        + x.other_allowances
                    )[0]
                    ts_cost_value = annual_ts_cost / work_hours
                    contract_cost_value = annual_ts_cost / work_hours
                else:
                    # get currency rate
                    currency_rate = 1
                    if employee.bamboo_currency_id != employee.currency_id:
                        currency_rate = self.env["res.currency"]._get_conversion_rate(
                            employee.bamboo_currency_id,
                            employee.currency_id,
                            employee.company_id,
                            fields.Date.today(),
                        )
                    # compute cost for contractors and outstaffs
                    if employee.paid_per == "year":
                        ts_cost_value = employee.pay_rate * currency_rate / work_hours
                        contract_cost_value = employee.pay_rate / work_hours
                    elif employee.paid_per == "month":
                        ts_cost_value = (
                            employee.pay_rate * currency_rate * 12 / work_hours
                        )
                        contract_cost_value = employee.pay_rate * 12 / work_hours
                    elif employee.paid_per == "hour":
                        ts_cost_value = employee.pay_rate * currency_rate
                        contract_cost_value = employee.pay_rate

                employee.hourly_cost = ts_cost_value
                employee.contract_pay_rate = contract_cost_value
        # update employees that had timesheet cost but now has employee_type
        # or paid_per that not provide calculation of timesheet cost
        empls_to_update = self.search(
            [
                ("id", "not in", empls_to_compute.ids),
                ("hourly_cost", "!=", "0.00"),
                ("contract_pay_rate", "!=", "0.00"),
            ]
        )
        if empls_to_update:
            empls_to_update.hourly_cost = 0
            empls_to_update.contract_pay_rate = 0


class EmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    bamboo_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        copy=False,
        default=lambda self: self.env.company.currency_id.id,
        groups="hr.group_hr_user",
    )

    contract_pay_rate = fields.Monetary(
        string="Contract Pay Rate", currency_field="bamboo_currency_id", default=0.0
    )

    account_asset_counterpart_id = fields.Many2one(
        "account.account",
        string="Account Asset Counterpart",
        check_company=True,
        help="Account used as counterpart for entries related to this asset.",
        store=True,
    )
    related_contact_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
    )
