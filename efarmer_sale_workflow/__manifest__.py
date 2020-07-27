{
    'name': 'Sale Workflow, eFarmer',

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
        'base_automation',
        'mail',
        'sale_crm',
        'sale_stock',
    ],

    'data': [
        'views/ir_actions_server.xml',
    ],
}
