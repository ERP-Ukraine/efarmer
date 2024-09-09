# See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Shopify Connector PRO',
    'summary': 'Export products and your current stock from Odoo, and get orders from Shopify. '
               'Update order status and provide tracking numbers to your customers. '
               'All this automatically and instantly.',
    'category': 'Sales',
    'version': '15.0.1.11.0',
    'images': [
        'static/description/images/banner.gif',
    ],
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'live_test_url': 'https://ventortech.atlassian.net/servicedesk/customer/portal/1/group/1/create/3',
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
        'wizard/sale_order_cancel_views.xml',
        # Views
        'views/sale_order_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_integration.xml',
        'views/fields/product_ecommerce_field.xml',
        'views/metafield_mapping_views.xml',
        # External
        'views/external/external_order_risk_views.xml',
        'views/external/external_sale_channel_views.xml',
        'views/external/menu.xml',
    ],
    'demo': [
    ],
    'external_dependencies': {
        'python': [
            'ShopifyAPI',
        ],
    },
    'installable': True,
    'application': True,
    "cloc_exclude": [
        "**/*"
    ]
}
