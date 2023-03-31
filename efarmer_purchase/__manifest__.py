# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Purchase',
    'version': '15.0.1.0.0',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
    ],
    'data': [
        # Security
        'security/security.xml',
        # Model Views
        'views/purchase_views.xml',
    ],
    'installable': True,
    'application': True,
}
