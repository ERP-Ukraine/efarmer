{
    'name': 'eFarmer',

    'version': '1.28',
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
        'base_automation',
        'contacts',
        'web',
        'mail',
        'sale',
        'stock',
        'sale_crm',
        'sale_stock',
        'sales_team',
        'account',
        'account_intrastat',
    ],

    'data': [
        'security/efarmer_sale_workflow_groups.xml',
        'security/ir.model.access.csv',
        'reports/layout.xml',
        'reports/pro_forma_invoice.xml',
        'reports/commercial_invoice.xml',
        'reports/account_commercial_invoice.xml',
        'reports/account_invoice_wo_downpayment.xml',
        'reports/stock_picking_templates.xml',
        'reports/stock_label.xml',
        'reports/device_label_50x30.xml',
        'reports/device_label_70x35.xml',
        'views/res_partner_views.xml',
        'views/stock_location_views.xml',
        'views/efarmer_client_type_views.xml',
        'views/efarmer_sale_workflow_menus.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/stock_warehouse_views.xml',
        'wizards/product_variant_replacement_wizard.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'efarmer_sale_workflow/static/src/js/inventory_report_list_controller.js',
        ],
    },
}
