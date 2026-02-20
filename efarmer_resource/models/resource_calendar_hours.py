# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import pytz
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api


MONTH_SELECTION = [
    ('01', 'January'),
    ('02', 'February'),
    ('03', 'March'),
    ('04', 'April'),
    ('05', 'May'),
    ('06', 'June'),
    ('07', 'July'),
    ('08', 'August'),
    ('09', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class ResourceCalendarHours(models.Model):
    _name = 'resource.calendar.hours'
    _description = 'Hours per Year'
    _rec_name = 'month'

    year = fields.Char(
        string='Year', compute="_compute_year", store=True
    )

    month = fields.Selection(
        MONTH_SELECTION,
        string='Month',
        required=True,
        default=lambda self: str(fields.Date.today().month).zfill(2)
    )

    total_hours = fields.Float(
        string='Total Hours',
        compute='_compute_hours',
    )

    working_hours = fields.Float(
        string='Working Hours',
        compute='_compute_hours',
    )

    resource_calendar_id = fields.Many2one(
        comodel_name='resource.calendar',
        string='Resource Calendar',
    )

    @api.depends("resource_calendar_id.year")
    def _compute_year(self):
        for record in self:
            record.year = record.resource_calendar_id.year

    @api.depends('resource_calendar_id', 'year', 'month')
    def _compute_hours(self):
        for record in self:
            calendar = record.resource_calendar_id
            tz = pytz.timezone(calendar.tz)
            start_date = tz.localize(fields.Datetime.from_string(
                '{}-{}-01'.format(record.year, record.month)
            ))
            end_date = start_date + relativedelta(months=1, seconds=-1)

            attendance_intervals = calendar._attendance_intervals_batch(
                start_date, end_date
            )[False]
            leave_intervals = calendar._leave_intervals_batch(
                start_date, end_date, None
            )[False]

            record.total_hours = sum(
                (stop - start).total_seconds() / 3600
                for start, stop, _ in attendance_intervals
            )

            work_intervals = attendance_intervals - leave_intervals
            record.working_hours = sum(
                (stop - start).total_seconds() / 3600
                for start, stop, _ in work_intervals
            )
