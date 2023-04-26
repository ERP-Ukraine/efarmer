# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
{
    'name': 'eFarmer Capitalization',
    'version': '1.30',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
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
