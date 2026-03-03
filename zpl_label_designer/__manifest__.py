# Copyright 2022 VentorTech OU
# See LICENSE file for full copyright and licensing details.

{
    'name': 'ZPL Label Designer PRO',
    'summary': """
        No-code ZPL label designer for Odoo. Design and print labels for products,
        inventory, sales, manufacturing, and barcode operations. Supports one-to-many,
        many-to-many fields, dynamic content, and custom formats. Works with Zebra and
        other ZPL-compatible printers. Integrates with Odoo Direct Print PRO for automated printing
        without IoT Box.
        Keywords: ZPL Label Designer | Zebra Label Odoo | Thermal Label Designer |
        Odoo Print Labels | ZPL Editor Odoo | Barcode Label Print | Product Labels Odoo |
        Print from Odoo | Odoo Label Creator |Odoo Zebra Printer | ZPL Template Odoo |
        Odoo Manufacturing Labels | Inventory Labeling Odoo | No-Code Label Design |
        Dynamic ZPL Labels | Custom Labels in Odoo | Direct Print Integration | ZPL Print Odoo |
        Label Generator for Odoo | Odoo Warehouse Labels
    """,
    'version': '19.0.1.3.5',
    'category': 'Tools',
    "images": ["static/description/images/banner.gif"],
    'author': 'VentorTech',
    'website': 'https://ecosystem.ventor.tech/product/zpl-label-designer-one-time-payment/',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'live_test_url': 'https://odoo.ventor.tech/',
    'price': 99.00,
    'currency': 'EUR',
    'depends': ['base', 'product', 'stock', 'product_expiry'],
    'data': [
        # Data
        'data/ir_config_parameter_data.xml',
        'data/ir_actions_server_data.xml',
        'data/label_allowed_models.xml',
        # Access rights
        'security/security.xml',
        'security/ir.model.access.csv',
        # Root menus
        'views/designer_menus.xml',
        # Views
        'views/label_designer_view.xml',
        'views/res_config_settings_views.xml',
        'wizard/product_label_layout.xml',
        'wizard/stock_lot_label_layout.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'zpl_label_designer/static/src/css/**/*',
            'zpl_label_designer/static/src/js/**/*',
            'zpl_label_designer/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
    "cloc_exclude": [
        "**/*",
    ],
    'uninstall_hook': 'uninstall_hook',
    'post_init_hook': 'post_init_hook',
}
