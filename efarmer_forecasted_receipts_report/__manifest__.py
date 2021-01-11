{
    'name': 'Forecasted Receipts Report, eFarmer',

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
        'contacts',
        'stock',
    ],

    'data': [
        'data/data.xml',
        'views/res_partner_views.xml',
    ],
}
