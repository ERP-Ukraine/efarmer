# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import datetime

from odoo import models, fields

from .resource_calendar_hours import MONTH_SELECTION


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    hours_per_year = fields.One2many(
        comodel_name='resource.calendar.hours',
        inverse_name='resource_calendar_id',
        string='Hours per Year',
        domain=lambda self: [('year', '=', self.year)],
        readonly=True,
    )

    year = fields.Selection(
        [(str(datetime.now().year+i), str(datetime.now().year+i)) for i in range(6)],
        string="Year",
        default=str(datetime.now().year),
        required=True,
    )

    def write(self, vals):
        if 'year' in vals and vals['year']:
            year = vals.get('year')
            month_hours = self.env['resource.calendar.hours'].search(
                [
                    ('year', '=', year),
                    ('resource_calendar_id', '=', self.id),
                ]
            )
            exist_months = month_hours.mapped('month')
            if not exist_months or (exist_months and len(exist_months) != 12):
                expected_month_list = [x[0] for x in MONTH_SELECTION]
                to_create = set(expected_month_list) - set(exist_months)
                for month in to_create:
                    self.hours_per_year.create(
                        {
                            'year': year,
                            'month': month,
                            'resource_calendar_id': self.id,
                        }
                    )

        return super(ResourceCalendar, self).write(vals)
