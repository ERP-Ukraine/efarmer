# See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo Shopify Connector PRO',
    'summary': '''Export products and your current stock from Odoo to Shopify, and seamlessly
import orders from your Shopify store into Odoo. Update order status and provide
tracking numbers to your customers automatically and instantly!

This Shopify connector simplifies multi-channel e-commerce by automating data transfer
between your Shopify store and Odoo. Reduce manual work, eliminate errors, and improve efficiency
with real-time synchronization of products, stock levels, and orders.

We also offer integrations with other popular e-commerce platforms, including Magento 2,
PrestaShop, and WooCommerce.

Keywords: Shopify, Shopify Odoo Integration, Sync Shopify with Odoo, Shopify Inventory Sync,
Shopify Order Import, Shopify Product Sync, Odoo Shopify Connector, Shopify Integration,
E-commerce Integration, Multi-Channel Selling, Seamless E-commerce Integration,
Multi-Store Management, Odoo E-commerce Solution, Multi-Channel Sales Management,
Connect Shopify to Odoo, Shopify Odoo Bridge, Odoo Shopify Bridge''',
    'category': 'Sales',
    'version': '19.0.2.1.0',
    'images': [
        'static/description/images/banner.gif',
    ],
    'author': 'VentorTech',
    'website': 'https://ecosystem.ventor.tech/product/odoo-shopify-connector-pro/',
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
        'wizard/integration_auth_shopify_views.xml',
        'wizard/configuration_wizard_shopify.xml',
        'wizard/sale_order_cancel_views.xml',
        'wizard/integration_product_pricelist_batch_views.xml',
        # Views
        'views/sale_order_views.xml',
        'views/sale_integration_input_file.xml',
        'views/delivery_carrier_views.xml',
        'views/product_template_views.xml',
        'views/product_product_views.xml',
        'views/sale_integration.xml',
        'views/fields/product_ecommerce_field.xml',
        'views/metafield_mapping_views.xml',
        # External
        'views/external/external_order_risk_views.xml',
        'views/external/external_sale_channel_views.xml',
        'views/external/external_order_source_name_views.xml',
        'views/external/external_integration_tag_views.xml',
        'views/external/integration_catalog_external_views.xml',
        'views/external/menu.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    "cloc_exclude": [
        "**/*",
    ]
}
