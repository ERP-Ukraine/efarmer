{
    'name': 'Shipping Report, eFarmer',

    'version': '1.1',
    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'AGPL-3',
    'auto_install': False,
    'installable': True,
    'application': True,

    'demo': [],

    'depends': [
        'stock',
        'sale_stock',
    ],

    'data': [
        'wizards/efarmer_shipping_report.xml',
    ],
}
