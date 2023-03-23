# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
{
    'name': 'eFarmer Invoice B2B Contactors',
    'version': '1.0',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
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
        'views/hr_employee_views.xml',
        'views/account_analytic_line_views.xml',
    ],
    'installable': True,
    'application': True,
}
