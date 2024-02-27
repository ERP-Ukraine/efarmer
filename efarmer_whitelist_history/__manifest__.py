# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer WhiteList',
    'version': '1.1',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'depends': [
        'base',
        'trilab_whitelist',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/whitelist_view.xml',
        'views/sale_order_view.xml',
        'views/res_partner.xml',
    ],
    'installable': True,
    'application': True,
}

