# See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Shopify Connector PRO',
    'summary': 'Export products and your current stock from Odoo, and get orders from Shopify. '
               'Update order status and provide tracking numbers to your customers. '
               'All this automatically and instantly.',
    'category': 'Sales',
    'version': '15.0.1.9.2',
    'images': [
        'static/description/images/banner.gif',
    ],
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'live_test_url': 'https://ventor.tech/contact-us/',
    'price': 449.00,
    'currency': 'EUR',
    'depends': [
        'integration',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/ir_config_parameter_data.xml',
        'data/product_ecommerce_fields.xml',
        # Wizard
        'wizard/configuration_wizard_shopify.xml',
        # Views
        'views/sale_order_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_integration.xml',
        'views/fields/product_ecommerce_field.xml',
        # External
        'views/external/external_order_risk_views.xml',
        'views/external/menu.xml',
    ],
    'demo': [
    ],
    'external_dependencies': {
        'python': [
            'shopify',
        ],
    },
    'installable': True,
    'application': True,
    "cloc_exclude": [
        "**/*"
    ]
}
