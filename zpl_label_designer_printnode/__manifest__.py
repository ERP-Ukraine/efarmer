# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

{
    'name': 'ZPL Label Designer + Odoo Direct Print Bridge',
    'summary': """
        Integration module between ZPL Label Designer and Direct Print modules,
    """,
    'version': '15.0.1.0.0',
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
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    "cloc_exclude": [
        "**/*",
    ]
}
