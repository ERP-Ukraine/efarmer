# -*- coding: utf-8 -*-

# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Sale Portal',
    'version': '1.0',
    'category': 'Others',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'efarmer_sale_workflow',
    ],
    'description': "",
    'data': [
        # Security
        # 'security/ir.model.access.csv',
        # Model Views
        'views/sale_portal_templates.xml',
    ],

    'auto_install': False,
    'installable': True,
    'application': True,
}
