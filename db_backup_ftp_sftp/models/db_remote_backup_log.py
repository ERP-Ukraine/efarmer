# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models

from .db_remote_backup import human_size


class DbRemoteBackupLog(models.Model):
    """One upload of one backup file."""
    _name = 'db.remote.backup.log'
    _description = 'Backup History'
    _order = 'upload_date desc, id desc'

    config_id = fields.Many2one('db.remote.backup', string='Destination',
                                required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Source File', readonly=True)
    # Float (double precision): an Integer column overflows at 2 GB
    size = fields.Float(string='Source Size (bytes)', readonly=True)
    mtime = fields.Float(string='Source Modified (epoch)', readonly=True)
    uploaded_size = fields.Float(readonly=True)
    size_display = fields.Char(string='Size', compute='_compute_size_display')
    remote_path = fields.Char(string='Remote Path', readonly=True)
    state = fields.Selection([
        ('uploaded', 'Uploaded'),
        ('failed', 'Failed'),
        ('deleted', 'Deleted (retention)'),
    ], string='Status', readonly=True, index=True)
    upload_date = fields.Datetime(string='Date', readonly=True)
    deleted_date = fields.Datetime(string='Deleted On', readonly=True)
    duration = fields.Float(string='Duration (s)', readonly=True)
    message = fields.Text(readonly=True)

    @api.depends('size', 'uploaded_size')
    def _compute_size_display(self):
        for rec in self:
            rec.size_display = human_size(rec.uploaded_size or rec.size)
