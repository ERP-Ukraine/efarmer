# -*- coding: UTF-8 -*-
# Copyright 2026 Solvve, Inc. <sales@solvve.com>

{
    "name": "HubSpot. Quotation Connector",
    "version": "19.0.1.0.0",
    "summary": "Quotation Connector",
    "description": "",
    "category": "",
    "author": "Solvve, Inc., VentorTech",
    "website": "https://solvve.com, https://ventor.tech",
    "license": "OPL-1",
    "depends": [
        "base",
        "sale_management",
        "sale_margin",
        "efarmer_sale_workflow",
    ],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_actions_server_data.xml",
        "data/ir_config_parameter_data.xml",
        "views/hubspot_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "wizard/assign_sale_deals_wizard_views.xml",
    ],
    "external_dependencies": {
        "python": ["hubspot-api-client"],
    },
}
