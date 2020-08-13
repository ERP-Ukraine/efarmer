# -*- coding: utf-8 -*-
{
    'name': 'Leads From External Websites',

    'version': '1.6',
    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',
    'auto_install': False,
    'installable': True,
    'application': True,

    'demo': [],

    'depends': [
        'base',
        'web',
        'crm',
        'sales_team',
        'utm_extended',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/external_website_form_field.xml',
        'views/external_website_form_tag.xml',
        'views/external_website_form.xml',
        'views/templates.xml',
    ],
}
