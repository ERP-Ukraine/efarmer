# -*- coding: utf-8 -*-

# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': 'Copy Odoo.sh Backups to SFTP / FTP',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'author': 'VentorTech',
    'website': 'https://ventor.tech',
    'summary': 'Copy the daily backups Odoo.sh already makes (~/backup.daily) '
               'to an SFTP or FTP/FTPS server',
    'description': """
        Odoo.sh keeps its daily backups in ~/backup.daily inside the production
        container. This module copies those files to your own SFTP or FTP/FTPS.
    """,
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/db_remote_backup_views.xml',
        'views/db_remote_backup_log_views.xml',
        'views/menus.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
