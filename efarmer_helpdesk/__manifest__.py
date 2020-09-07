{
    'name': 'Helpdesk, eFarmer',

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
        'helpdesk',
        'stock',
        'helpdesk_stock',
    ],

    'data': [
        'views/stock_production_lot_views.xml',
    ],
}
