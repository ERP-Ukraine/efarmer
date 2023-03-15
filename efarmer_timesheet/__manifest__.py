# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    'name': 'Timesheet eFarmer',
    'version': '15.0.1.0.1',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_timesheet',
    ],
    'data': [
        # Initial Data
        'data/ir_cron_data.xml',
        # Model Views
        'views/hr_views.xml',
    ],
    'installable': True,
    'application': True,
}
