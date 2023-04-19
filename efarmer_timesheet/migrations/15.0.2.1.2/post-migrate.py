# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def update_timesheet_rate_per_hour(env):
    youtrack_timesheets = env['account.analytic.line'].search([
        '|',
        ('rate_per_hour', '=', False),
        ('rate_per_hour', '=', 0),
        ('youtrack_id', '!=', False),
        ('unit_amount', '!=', 0),
    ])
    for timesheet in youtrack_timesheets:
        timesheet.rate_per_hour = abs(timesheet.amount / timesheet.unit_amount)

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, dict())
    update_timesheet_rate_per_hour(env)
