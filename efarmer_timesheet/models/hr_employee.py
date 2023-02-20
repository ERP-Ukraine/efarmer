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

    annual_gross_salary = fields.Monetary(
        string='Annual Gross Salary',
        currency_field='currency_id',
    )