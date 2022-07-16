{
    'name': 'Flexbe',

    'version': '2.0',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',
    'auto_install': False,
    'installable': False,
    'application': True,

    'demo': [],

    'depends': [
        'base',
        'crm',
        'utm2',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/crm_lead_views.xml',
        'views/flexbe_domain_views.xml',
        'views/res_config_settings.xml',
    ],
}
