# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Capitalization',
    'version': '1.30',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Project',
    'depends': [
        'account',
        'account_asset',
        'base',
        'efarmer_timesheet',
        'efarmer_youtrack',
        'product',
        'project',
        'hr',
        'hr_timesheet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_capitalization_views.xml',
    ],
    'installable': True,
    'application': True,
}
