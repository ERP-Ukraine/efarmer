# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
{
    'name': 'eFarmer Capitalization',
    'version': '1.0',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'category': 'Project',
    'depends': [
        'base',
        'project',
        'hr_timesheet',
        'product',
        'account',
        'account_asset',
        'efarmer_youtrack',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_capitalization_views.xml',
    ],
    'installable': True,
    'application': True,
}
