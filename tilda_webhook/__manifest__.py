{
    'name': 'Tilda (Webhook)',
    'version': '1.0',
    'summary': 'Get leads and orders from Tilda service via webhook technology.',

    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',

    'auto_install': False,
    'application': False,
    'installable': True,

    'demo': [],
    'data': [
        'security/tilda_website_groups.xml',
        'security/ir.model.access.csv',
        'views/tilda_website_field_views.xml',
        'views/tilda_website_views.xml',
        'views/tilda_website_menus.xml',
    ],

    'depends': [
        'crm',
    ],
}
