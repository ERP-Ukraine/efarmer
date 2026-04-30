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
        Keywords: Odoo Direct Print | Odoo Print Module | Print Directly from Odoo |
        Odoo Printing Solution | Local Printer Integration | Bluetooth Printer Odoo |
        Wi-Fi Printer Odoo | Print Shipping Labels Odoo | Cloud Printing Odoo |
        Print Reports from Odoo | Barcode Printing Odoo | PDF Printing Odoo |
        ERP Printing Solution | PrintNode Alternative | Seamless Printing in Odoo |
        Direct Printing in Odoo | Print Custom Labels Odoo | Print Without Downloading |
        Automatic Printing Odoo | Fast Printing from Odoo | Thermal Printer Odoo |
        ZPL Printer Support | Print Label | Print Document | Print Order | Print Transfer|
        Print PDF | Print ZPL | Print Invoice | Print Price | Print Purchase | Print Barcode |
        Print Picking | Print Package | Print Lot | Print Serial | Auto Print | Auto Printing |
        Print Scenario | Warehouse Printing | Remote Printing | Network Printing | Print Agent |
        Print Assistant | Advanced Printing | POS | Multi Printing | Print Attachment | POS Print |
        Print Serial Number | ZPL Label Print | Zebra Printer Odoo | Odoo Label Printing |
        Direct Print Labels | Thermal Label Printing | Auto Print Odoo | Label Printer Integration |
        Odoo Barcode Print | Odoo Label Designer | Print from Odoo | Odoo Print Bridge |
        Network Label Printing | USB Printer Odoo | Odoo Manufacturing Labels | No IoT Box |
        Inventory Label Printing | ZPL Print from Odoo | Odoo Print Automation | ZPL Label Designer |
        Zebra Label Odoo | Thermal Label Designer | Odoo Print Labels | ZPL Editor Odoo |
        Barcode Label Print | Product Labels Odoo | Odoo Label Creator | Odoo Zebra Printer |
        ZPL Template Odoo | Inventory Labeling Odoo | No-Code Label Design | Dynamic ZPL Labels |
        Custom Labels in Odoo | Direct Print Integration | ZPL Print Odoo | Label Generator for Odoo |
        Odoo Warehouse Labels | ZPL Designer | Create Label | Stock Label | Lot Label | Serial Label |
        Odoo ZPL | Designer Label | Creating Label | Create ZPL | Document Label | Package Label |
        Packaging Label | Price Label | Label Builder
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
