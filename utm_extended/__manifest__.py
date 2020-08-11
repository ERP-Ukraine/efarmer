# -*- coding: utf-8 -*-
{
    'name': 'Extended UTM',
    'summary': 'Support utm_content and utm_term parameters.',

    'version': '1.0',
    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',
    'auto_install': False,
    'installable': True,
    'application': False,

    'demo': [],

    'depends': [
        'base',
        'utm',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/utm_content.xml',
        'views/utm_term.xml',
    ],
}
