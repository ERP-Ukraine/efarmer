# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Attachment access',
    'version': '1.1',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Other',
    'depends': [
        'base',
    ],
    'data': [
        'security/res_groups.xml',
        'security/rules.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'application': False,
}

