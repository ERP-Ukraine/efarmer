{
    'name': 'Sale Workflow, eFarmer',

    'version': '1.11',
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
    ],

    'data': [
        'security/efarmer_sale_workflow_groups.xml',
        'security/ir.model.access.csv',
        'reports/commercial_invoice.xml',
        'reports/stock_picking_templates.xml',
        'views/assets.xml',
        'views/ir_actions_server_views.xml',
        'views/res_partner_views.xml',
        'views/stock_location_views.xml',
        'views/efarmer_client_type_views.xml',
        'views/efarmer_sale_workflow_menus.xml',
        'views/product_template_views.xml',
        'views/account_move_views.xml',
    ],
}
