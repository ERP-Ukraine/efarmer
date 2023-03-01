# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import datetime
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.addons.resource.models.resource import Intervals
from ..models.resource_calendar_hours import MONTH_SELECTION


class TestResourceCalendar(TransactionCase):
    def setUp(self):
        super(TestResourceCalendar, self).setUp()

        self.company = self.env['res.company'].create(
            {
                'name': 'Test Company',
            }
        )
        self.resource_calendar = self.env['resource.calendar'].create({
            'company_id': self.company.id,
            'name': 'Test Calendar',
            'tz': 'Europe/Brussels',
        })
        self.year = str(datetime.now().year)

    def _create_patch_object(self, target, attribute):
        patcher = patch.object(target, attribute)
        thing = patcher.start()
        self.addCleanup(patcher.stop)
        return thing

    def test_create_hours_per_year(self):
        self.resource_calendar.write({'year': self.year})

        month_hours = self.env['resource.calendar.hours'].search(
            [
                ('year', '=', self.year),
                ('resource_calendar_id', '=', self.resource_calendar.id),
            ]
        )
        self.assertEqual(len(month_hours), 12)
        for month in MONTH_SELECTION:
            self.assertTrue(month_hours.filtered(lambda x: x.month == month[0]))

    def test_create_hours_per_year_with_existing_months(self):
        vals = {
            'year': self.year,
            'month': '01',
            'resource_calendar_id': self.resource_calendar.id,
        }
        self.resource_calendar.hours_per_year.create(vals)

        vals.update({'month': '02'})
        self.resource_calendar.hours_per_year.create(vals)

        month_hours = self.env['resource.calendar.hours'].search(
            [
                ('year', '=', self.year),
                ('resource_calendar_id', '=', self.resource_calendar.id),
            ]
        )
        self.assertEqual(len(month_hours), 2)
        self.assertEqual(set(month_hours.mapped('month')), {'01', '02'})

        self.resource_calendar.write({'year': self.year})

        month_hours = self.env['resource.calendar.hours'].search(
            [
                ('year', '=', self.year),
                ('resource_calendar_id', '=', self.resource_calendar.id),
            ]
        )
        self.assertEqual(len(month_hours), 12)
        for month in MONTH_SELECTION:
            self.assertTrue(month_hours.filtered(lambda x: x.month == month[0]))

    def test_total_and_working_hours(self):

        month_hours = self.resource_calendar.hours_per_year.create({
            'year': self.year,
            'month': '01',
            'resource_calendar_id': self.resource_calendar.id,
        })

        mock_att_intervals = self._create_patch_object(
            type(self.env['resource.calendar']),
            '_attendance_intervals_batch'
        )
        mock_leave_intervals = self._create_patch_object(
            type(self.env['resource.calendar']),
            '_leave_intervals_batch'
        )
        mock_att_intervals.return_value = {
            False: Intervals(
                [
                    (
                        datetime(2023, 1, 2, 8, 0),
                        datetime(2023, 1, 2, 12, 0),
                        self.env['resource.calendar.attendance']
                    ),
                    (
                        datetime(2023, 1, 2, 13, 0),
                        datetime(2023, 1, 2, 17, 0),
                        self.env['resource.calendar.attendance']
                    ),
                ]
            )
        }
        mock_leave_intervals.return_value = {
            False: Intervals(
                [
                    (
                        datetime(2023, 1, 2, 14, 0),
                        datetime(2023, 1, 2, 15, 0),
                        self.env['resource.calendar.leaves']
                    ),
                ]
            )
        }

        month_hours._compute_hours()

        self.assertEqual(month_hours.total_hours, 8)
        self.assertEqual(month_hours.working_hours, 7)
