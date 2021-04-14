{
    'name': 'Extended UTM features',

    'version': '1.0',
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
        'utm',
        'crm',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/crm_lead_views.xml',
        'views/utm_content_views.xml',
        'views/utm_term_views.xml',
    ],
}
