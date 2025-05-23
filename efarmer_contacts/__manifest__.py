# Copyright 2024 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Contacts',
    'version': '1.1',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': [
        'base',
        'account',
        'base_vat',
        'account_consolidation',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
}
