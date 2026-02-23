# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    'name': 'eFarmer Resource',
    'version': '19.0.1.0.0',
    'category': 'Other',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'license': 'LGPL-3',
    'depends': [
        'resource'
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Model Views
        'views/resource_calendar_views.xml',
    ],
    'installable': True,
    'application': True,
}
