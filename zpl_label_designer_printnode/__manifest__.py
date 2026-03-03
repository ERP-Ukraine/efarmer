# Copyright 2022 VentorTech OU
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Direct Print PRO + ZPL Label Designer PRO',
    'summary': """
        Bridge module to connect Odoo Direct Print PRO with ZPL Label Designer.
        Enables automatic printing of ZPL labels (Zebra, thermal, network printers)
        without IoT Box.
        Supports label printing from Inventory, Sales, Barcode, Manufacturing.
        Includes print automation, multi-language printing, and compatibility with USB, Wi-Fi,
        and network printers. Works on Odoo Community, Enterprise, Odoo.sh.
        Keywords: ZPL Label Print | Zebra Printer Odoo | Odoo Label Printing |
        Direct Print Labels | Thermal Label Printing | Auto Print Odoo |
        Label Printer Integration | Odoo Barcode Print | Odoo Label Designer |
        Print from Odoo | Odoo Print Bridge | No IoT Box | Network Label Printing |
        USB Printer Odoo | Odoo Manufacturing Labels | Inventory Label Printing |
        ZPL Print from Odoo | Odoo Print Automation
    """,
    'version': '19.0.1.2.0',
    'category': 'Tools',
    "images": ["static/description/images/banner.gif"],
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'live_test_url': 'https://odoo.ventor.tech/',
    'price': 0.00,
    'currency': 'EUR',
    'depends': ['zpl_label_designer', 'printnode_base'],
    'data': [
        # Views
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    "cloc_exclude": [
        "**/*",
    ]
}
