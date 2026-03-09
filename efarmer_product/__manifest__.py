# -*- coding: utf-8 -*-

# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "eFarmer Product",
    "version": "19.0.1.0.0",
    "category": "Others",
    "author": "VentorTech",
    "website": "https://ventor.tech",
    "license": "LGPL-3",
    "depends": [
        "account",
        "account_reports",
        "sale",
        "stock",
        "stock_account",
        "helpdesk",
        "helpdesk_sale",
        "mrp",
        "product",
    ],
    "description": "",
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Model Views
        "views/res_config_settings.xml",
        "views/product_function_views.xml",
        "views/product_template_views.xml",
        "views/product_vat_views.xml",
        "views/sale_order_views.xml",
        # "views/account_fiscal_position_views.xml",
        # "views/stock_valuation_layer_views.xml",
        "views/res_users_views.xml",
    ],
    "auto_install": False,
    "installable": True,
    "application": True,
}
