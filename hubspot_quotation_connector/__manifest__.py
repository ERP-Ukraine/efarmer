# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

{
    'name': 'HubSpot. Quotation Connector',
    'version': '15.0.0.0.1',
    'summary': 'Quotation Connector',
    'description': '',
    'category': '',
    'author': 'Solvve, Inc.',
    'website': 'https://solvve.com',
    'license': 'OPL-1',
    'depends': [
        'base',
        'sale_management',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/hubspot_config_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {
        'python': ['hubspot-api-client'],
    }
}
