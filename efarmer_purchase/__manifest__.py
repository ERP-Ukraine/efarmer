# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'eFarmer Purchase',
    'version': '19.0.1.3.0',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'purchase',
        'purchase_advance_payment',
        'mrp',
        'hr',
        'purchase_order_line_menu',
        'account_analytic_tag'
    ],
    'data': [
        # Security
        'security/security.xml',
        # Model Views
        'views/purchase_views.xml',
        'views/res_company_views.xml',
        'views/mrp_production_view.xml',
        'views/res_user_views.xml',
        'report/purchase_report_views.xml',
    ],
    'installable': True,
    'application': True,
}
