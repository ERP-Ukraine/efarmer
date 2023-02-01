# Copyright 2023 VentorTech OU
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Odoo YouTrack Integration',
    'summary': """
        Integration between Odoo and YouTrack system
    """,
    'version': '15.0.0.1.0',
    'category': 'Other',
    # "images": ["static/description/images/logo.gif"],
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'OPL-1',
    'depends': [
        'project',
        'account_asset',
    ],
    'data': [
        # Security
        # 'security/security.xml',
        'security/ir.model.access.csv',
        # Initial Data
        # 'data/ir_actions_server_data.xml',
        # Model Views
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/youtrack_integration_views.xml',
        'views/youtrack_integration_menus.xml',
    ],
    'installable': True,
    'application': True,
}
