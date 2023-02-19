{
    'name': 'Helpdesk, eFarmer',

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
        'helpdesk',
        'helpdesk_fsm',
        'stock',
        'helpdesk_stock',
        'helpdesk_sale',
        'efarmer_sale_workflow',
    ],

    'data': [
        'views/stock_production_lot_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
}
