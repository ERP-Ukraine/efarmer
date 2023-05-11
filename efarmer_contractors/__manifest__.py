# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Invoice B2B Contactors',
    'version': '1.1',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Project',
    'depends': [
        'project',
        'hr_timesheet',
        'account',
        'analytic',
        'account_asset',
        'efarmer_youtrack',
        'hr',
        'efarmer_timesheet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_contractors_views.xml',
        'views/project_contractors_line_views.xml',
    ],
    'installable': True,
    'application': True,
}
