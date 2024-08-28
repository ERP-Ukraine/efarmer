# See LICENSE file for full copyright and licensing details.

{
    'name': 'Integration',
    'version': '15.0.1.17.0',
    'category': 'Hidden',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'support': 'support@ventor.tech',
    'license': 'OPL-1',
    'price': 50.00,
    'currency': 'EUR',
    'images': ['static/description/icon.png'],
    'summary': 'Sale Integration with External Services',
    'depends': [
        'web',
        'mrp',
        'sale',
        'delivery',
        'queue_job',
    ],
    'external_dependencies': {
        'python': [
            'python-stdnum',
        ],
    },
    'data': [
        # Security
        'security/integration_security.xml',
        'security/ir.model.access.csv',

        # data
        'data/queue_job_channel_data.xml',
        'data/queue_job_function_data.xml',
        'data/ir_config_parameter_data.xml',
        'data/ir_cron_data.xml',
        'data/res_partner_category.xml',
        'data/ir_actions_server_data.xml',
        'data/product_ecommerce_fields.xml',
        'data/mail_template_data.xml',
        'data/res_config_data.xml',

        # Wizard
        'wizard/import_customers_wizard.xml',
        'wizard/refresh_products_wizard.xml',
        'wizard/import_stock_levels_wizard.xml',
        'wizard/integration_pricelist_wizard_views.xml',
        'wizard/message_wizard.xml',
        'wizard/configuration_wizard.xml',
        'wizard/external_integration_wizard.xml',
        'wizard/import_export_integration_wizard.xml',
        'wizard/integration_import_product_wizard.xml',
        'wizard/integration_installation_wizard.xml',

        # Views
        'views/sale_integration.xml',
        'views/sale_integration_api_fields.xml',
        'views/sale_integration_input_file.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_sub_status.xml',
        'views/sale_order_payment_method_views.xml',
        'views/product_public_category_views.xml',
        'views/product_image_views.xml',
        'views/product_product_views.xml',
        'views/product_pricelist_views.xml',
        'views/product_feature_views.xml',
        'views/product_feature_value_views.xml',
        'views/product_attribute_views.xml',
        'views/queue_job.xml',
        'views/job_log_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_tax_views.xml',
        'views/account_move_views.xml',

        # External
        'views/external/integration_account_tax_group_external_views.xml',
        'views/external/integration_account_tax_external_views.xml',
        'views/external/integration_product_attribute_external_views.xml',
        'views/external/integration_product_attribute_value_external_views.xml',
        'views/external/integration_product_feature_external_views.xml',
        'views/external/integration_product_feature_value_external_views.xml',
        'views/external/integration_delivery_carrier_external_views.xml',
        'views/external/integration_product_template_external_views.xml',
        'views/external/integration_product_product_external_views.xml',
        'views/external/integration_res_country_external_views.xml',
        'views/external/integration_res_country_state_external_views.xml',
        'views/external/integration_res_lang_external_views.xml',
        'views/external/integration_sale_order_payment_method_external_views.xml',
        'views/external/integration_product_public_category_external_views.xml',
        'views/external/integration_res_partner_external_views.xml',
        'views/external/integration_sale_order_external_views.xml',
        'views/external/integration_sale_order_sub_status_external_views.xml',
        'views/external/integration_product_pricelist_external_views.xml',
        'views/external/integration_product_pricelist_item_external_views.xml',
        'views/external/integration_stock_location_external_views.xml',
        'views/external/external_integration_tag_views.xml',
        'views/external/external_order_transaction_views.xml',
        'views/external/external_order_fulfillment_views.xml',

        # Mappings
        'views/mappings/integration_account_tax_mapping_views.xml',
        'views/mappings/integration_product_attribute_mapping_views.xml',
        'views/mappings/integration_product_attribute_value_mapping_views.xml',
        'views/mappings/integration_product_feature_mapping_views.xml',
        'views/mappings/integration_product_feature_value_mapping_views.xml',
        'views/mappings/integration_delivery_carrier_mapping_views.xml',
        'views/mappings/integration_product_template_mapping_views.xml',
        'views/mappings/integration_product_product_mapping_views.xml',
        'views/mappings/integration_res_country_mapping_views.xml',
        'views/mappings/integration_res_country_state_mapping_views.xml',
        'views/mappings/integration_res_lang_mapping_views.xml',
        'views/mappings/integration_sale_order_payment_method_mapping_views.xml',
        'views/mappings/integration_product_public_category_mapping_views.xml',
        'views/mappings/integration_res_partner_mapping_views.xml',
        'views/mappings/integration_sale_order_mapping_views.xml',
        'views/mappings/integration_sale_order_sub_status_mapping_views.xml',
        'views/mappings/integration_product_pricelist_mapping_views.xml',

        # Product fields
        'views/fields/product_ecommerce_field.xml',
        'views/fields/product_ecommerce_field_mapping.xml',

        # Auto work-flow views
        'views/auto_workflow/integration_sale_order_sub_status_external_views.xml',
        'views/auto_workflow/integration_sale_order_payment_method_external_views.xml',
        'views/auto_workflow/integration_workflow_pipeline_views.xml',

        # Menu items
        'views/sale_integration_menu.xml',
        'views/auto_workflow/menu.xml',
        'views/external/menu.xml',
        'views/mappings/menu.xml',
        'views/fields/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'integration/static/src/**/*.css',
            'integration/static/src/**/*.js',
        ],
        'web.assets_qweb': [
            'integration/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    "cloc_exclude": [
        "**/*"
    ],
    'post_init_hook': 'post_init_hook',
}
