# -*- coding: utf-8 -*-
{
    'name': 'Extended UTM, Documents',
    'summary': 'Provide utm_content and utm_term for leads, so, invoices.',

    'version': '1.0',
    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',

    'auto_install': True,
    'installable': True,
    'application': False,

    'demo': [],

    'depends': [
        'utm_extended',
        'crm',
        'sale',
        'account',
        'sale_crm',
    ],

    'data': [
        'views/crm_lead.xml',
        'views/sale_order.xml',
        'views/account_move.xml',
    ],
}
