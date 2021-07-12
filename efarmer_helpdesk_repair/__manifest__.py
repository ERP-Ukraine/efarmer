{
    'name': 'Helpdesk Repair, eFarmer',

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
        'base',
        'stock',
        'helpdesk',
        'helpdesk_stock',
    ],

    'data': [
        'security/ir.model.access.csv',
        'wizards/efarmer_helpdesk_repair_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/stock_warehouse_lot_views.xml',
    ],
}
