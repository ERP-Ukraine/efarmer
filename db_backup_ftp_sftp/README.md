# Copy Odoo.sh Backups to SFTP / FTP (Odoo 18)

Odoo.sh keeps its daily backups in `~/backup.daily` inside the production
container. This module copies those files to your own SFTP or FTP/FTPS server.
It does not create a new dump and does not need SSH access to Odoo.sh or the
build ID: it runs inside Odoo, so it keeps working after every deploy.
