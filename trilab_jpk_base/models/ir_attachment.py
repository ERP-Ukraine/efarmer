from pathlib import Path

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import ormcache


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    x_full_path = fields.Char(compute='x_compute_full_path')

    @ormcache('self.store_fname')
    def x_get_full_path(self) -> Path:
        self.ensure_one()

        if not self.store_fname:
            # attachment content is stored in the database, there is no on-disk file
            raise UserError(_('Attachment %s is not stored on the filesystem.', self.display_name))

        return (Path(tools.config.filestore(self.env.cr.dbname)) / self.store_fname).absolute()

    @api.depends('store_fname')
    def x_compute_full_path(self):
        for attachment_id in self:
            attachment_id.x_full_path = attachment_id.store_fname and attachment_id.x_get_full_path()
