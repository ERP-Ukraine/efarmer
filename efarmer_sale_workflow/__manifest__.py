{
    'name': 'Sale Workflow, eFarmer',

    'version': '1.1',
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
        'base_automation',
        'web',
        'mail',
        'sale',
        'sale_crm',
        'sale_stock',
    ],

    'data': [
        'reports/commercial_invoice.xml',
        'views/ir_actions_server.xml',
    ],
}
