# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    'name': 'Odoo YouTrack Integration',
    'summary': """
        Integration between Odoo and YouTrack system
    """,
    'version': '15.0.1.0.0',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'hr_timesheet',
        'project',
        'account_asset',
        'queue_job',
    ],
    'data': [
        # Initial Data
        'data/ir_cron_data.xml',
        'data/work_type_demo.xml',
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Model Views
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/youtrack_integration_views.xml',
        'views/youtrack_issue_type_views.xml',
        'views/youtrack_product_version_views.xml',
        'views/hr_timesheet_views.xml',
        'views/youtrack_work_type_views.xml',
    ],
    'installable': True,
    'application': True,
}
