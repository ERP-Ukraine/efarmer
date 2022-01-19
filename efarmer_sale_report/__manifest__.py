{
    'name': 'Sale Report, eFarmer',

    'version': '1.0',
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
        'sale',
        'sale_margin',
    ],

    'data': [
        'security/ir.model.access.csv',
        'reports/efarmer_sale_report.xml',
    ],
}
