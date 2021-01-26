{
    'name': 'Stock Weekly Report, eFarmer',

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
        'contacts',
        'stock',
        'purchase',
        'purchase_stock',
    ],

    'data': [
        'data/data.xml',
        'views/res_partner_views.xml',
        'views/stock_location_views.xml',
        'views/menus.xml',
    ],

}
