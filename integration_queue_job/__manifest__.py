# Copyright (c) 2015-2016 ACSONE SA/NV
# Copyright (c) 2016 Camptocamp SA
# Copyright (c) 2025 VentorTech (https://ventor.tech)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'Integration Queue Job',
    'summary': '''Lightweight background jobs module used as a technical dependency for VentorTech integration modules.
Built on top of Job Queue module from OCA (https://github.com/OCA/queue).
''',
    'version': '19.0.1.0.3',
    'images': [
        'static/description/images/banner.gif',
    ],
    'author': 'VentorTech, Odoo Community Association (OCA), ACSONE SA/NV, Camptocamp',
    'website': 'https://github.com/ventor-dev/integration-queue',
    'license': 'LGPL-3',
    'category': 'Tools',
    'depends': ['mail', 'base_sparse_field', 'web'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/queue_job_views.xml',
        'views/queue_job_channel_views.xml',
        'views/queue_job_function_views.xml',
        'wizards/queue_jobs_to_done_views.xml',
        'wizards/queue_jobs_to_cancelled_views.xml',
        'wizards/queue_requeue_job_views.xml',
        'data/queue_data.xml',
    ],
    'installable': True,
    'application': False,
    'maintainers': ['ventor-dev'],
    'post_init_hook': 'post_init_hook',
    'post_load': 'post_load',
}
