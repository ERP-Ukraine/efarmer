# -*- coding: utf-8 -*-
{
    'name': 'eFarmer Stock',
    'version': '1.0',
    'category': 'Inventory',
    'author': 'VentorTech',
    'website': 'https://ventor.tech/',
    'license': 'LGPL-3',
    'depends': ['stock', 'mrp'],
    'description': '',
    'data': [
        'views/stock_production_lot_views.xml',
        'views/mrp_production_form_views.xml',
    ],
    'auto_install': False,
    'installable': True,
    'application': False,
}
