# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    'name': 'Efarmer Trilab Extension',
    'summary': """
        Module is designed to change and improve
        the functionality of the Trilab Modules
    """,
    'version': '18.0.1.0.1',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'efarmer_sale_workflow',
        'trilab_jpk_base',
        'trilab_invoice',
        'trilab_jpk_vat',
        'mrp',
    ],
    'data': [
        # Model Views
        'data/trilab_vat_reports.xml',
        'views/jpk_vat7m_templates.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
}
