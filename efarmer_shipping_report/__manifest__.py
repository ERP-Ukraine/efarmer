{
    'name': 'Shipping Report, eFarmer',

    "version": '19.0.1.0.0',
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
        'security/ir.model.access.csv',
        'wizards/efarmer_shipping_report.xml',
    ],
}
