# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    'name': 'Efarmer Advance Payment Extension',
    'summary': """
        Module is designed to change and improve
        the functionality of the OCA Module
        "Purchase Advance Payment"
    """,
    'version': '15.0.1.0.0',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'efarmer_purchase',
        'purchase_advance_payment',
    ],
    'data': [
        # Model Views
        'views/purchase_views.xml',
        # Security
        'security/security.xml',
    ],
    'installable': True,
    'application': True,
}
