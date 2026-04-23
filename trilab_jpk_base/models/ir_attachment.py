from pathlib import Path

from odoo import api, fields, models, tools
from odoo.tools import ormcache


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    x_full_path = fields.Char(compute='x_compute_full_path')
    x_size = fields.Integer(compute='x_compute_full_path')

    @ormcache('self.store_fname')
    def x_get_full_path(self) -> Path:
        self.ensure_one()
        return (Path(tools.config.filestore(self.env.cr.dbname)) / self.store_fname).absolute()

    @api.depends('store_fname')
    def x_compute_full_path(self):
        filestore = Path(tools.config.filestore(self.env.cr.dbname))

        for attachment_id in self:
            full_path = filestore / attachment_id.store_fname
            attachment_id.x_full_path = full_path.absolute()
            attachment_id.x_size = full_path.stat().st_size
