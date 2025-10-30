# Copyright 2025 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
{
    'name': 'Efarmer Account',
    'version': '15.0.1.1.0',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': [
        'account',
        'hr',
    ],
    'description': '',
    'data': [
        'views/account_account_views.xml',
        'views/account_bank_statement_views.xml',
    ],
    'installable': True,
    'application': False,
}
